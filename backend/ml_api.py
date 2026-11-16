"""Read-only historical replay and verified experiment endpoints."""
from contextlib import closing
from functools import lru_cache
from pathlib import Path
import json
import sqlite3
from fastapi import APIRouter, HTTPException, Query


def router(predictions, results):
    api = APIRouter(prefix='/api')
    predictions, results = Path(predictions), Path(results)

    def read(name):
        path = results / name
        if not path.is_file():
            raise HTTPException(503, 'Experiment artifact not generated')
        return json.loads(path.read_text(encoding='utf-8'))

    def db():
        if not predictions.is_file():
            raise HTTPException(503, 'June predictions not generated')
        connection = sqlite3.connect(predictions.resolve().as_uri()+'?mode=ro', uri=True)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA mmap_size=268435456')
        connection.execute('PRAGMA cache_size=-65536')
        return connection

    @api.get('/experiments')
    def experiments():
        metrics = read('metrics.json')
        verification = read('verification.json')
        if not verification.get('passed'):
            raise HTTPException(503, 'Metrics have not passed verification')
        return {'metrics': metrics, 'verification': verification, 'groups': read('error_groups.json'),
                'engineering': json.loads((results.parent/'engineering/benchmark.json').read_text(encoding='utf-8')) if (results.parent/'engineering/benchmark.json').is_file() else None}

    @api.get('/risk/options')
    def options(origin: str | None = Query(None, pattern=r'^[A-Z]{3}$'), dest: str | None = Query(None, pattern=r'^[A-Z]{3}$'), carrier: str | None = Query(None, pattern=r'^[A-Z0-9()]{2,6}$')):
        with closing(db()) as connection:
            def distinct(column, pairs):
                where = [(key, value) for key, value in pairs if value]
                sql = 'SELECT DISTINCT '+column+' FROM predictions'
                if where: sql += ' WHERE '+' AND '.join(key+'=?' for key, _ in where)
                return [r[0] for r in connection.execute(sql+' ORDER BY '+column, [value for _, value in where])]
            return {'origins': distinct('Origin', []), 'destinations': distinct('Dest', [('Origin',origin)]),
                    'carriers': distinct('Reporting_Airline', [('Origin',origin),('Dest',dest)]),
                    'dates': distinct('FlightDate', [('Origin',origin),('Dest',dest),('Reporting_Airline',carrier)])}

    @api.get('/risk/flights')
    def flights(origin: str = Query(..., pattern=r'^[A-Z]{3}$'), dest: str = Query(..., pattern=r'^[A-Z]{3}$'), carrier: str = Query(..., pattern=r'^[A-Z0-9()]{2,6}$'), date: str = Query(..., pattern=r'^2024-06-(0[1-9]|[12][0-9]|30)$')):
        with closing(db()) as connection:
            rows = connection.execute('SELECT flight_id, FlightDate, Flight_Number_Reporting_Airline, CRSDepTime, CRSArrTime, Origin, Dest, Reporting_Airline FROM predictions WHERE Origin=? AND Dest=? AND Reporting_Airline=? AND FlightDate=? ORDER BY CRSDepTime,flight_id LIMIT 100', [origin,dest,carrier,date]).fetchall()
        return {'flights':[dict(row) for row in rows], 'mode':'historical-backtest', 'limit':100}

    @api.get('/risk/flight/{flight_id}')
    def flight(flight_id: str, reveal: bool = False):
        import re
        if not re.fullmatch(r'[a-f0-9]{64}',flight_id): raise HTTPException(422,'Invalid flight identifier')
        with closing(db()) as connection:
            row = connection.execute('SELECT * FROM predictions WHERE flight_id=?',[flight_id]).fetchone()
        if row is None: raise HTTPException(404,'No supported historical flight')
        result = dict(row)
        label = result.pop('label')
        metrics = read('metrics.json')
        selected = metrics['selection']
        model = selected['recommended_model']
        threshold = selected['selected'][model]['validation']['threshold']
        result.update({'model':model, 'version':metrics['version'], 'score':result['score_'+model], 'threshold':threshold,
                       'predicted_delayed': result['score_'+model] >= threshold,
                       'mode':'historical-backtest', 'historical_reference':result['hist_route_rate']})
        if reveal: result['actual_delayed'] = bool(label)
        return result

    @api.get('/risk/examples')
    def examples():
        return {'cases':[{'flight_id':r['flight_id'],'origin':r['Origin'],'dest':r['Dest'],'date':r['FlightDate']} for r in read('cases.json')],
                'selection':'deterministic illustrative test examples; not representative sampling'}
    return api
