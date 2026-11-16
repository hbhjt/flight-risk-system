import json, sqlite3
from fastapi.testclient import TestClient
from backend.app import create_app


def test_replay_hides_outcome_and_restricts_supported_flights(tmp_path):
    columns=['flight_id','FlightDate','Reporting_Airline','Flight_Number_Reporting_Airline','Origin','Dest','CRSDepTime','CRSArrTime','dep_hour','Distance','CRSElapsedTime','label','history_cutoff_month','hist_route_count','hist_origin_count','hist_carrier_count','hist_route_rate','hist_origin_rate','hist_carrier_rate','score_B0','score_B1','score_B2','score_B3']
    schema='CREATE TABLE predictions ('+','.join(name+' '+('TEXT' if i in [0,1,2,3,4,5,12] else 'REAL') for i,name in enumerate(columns))+')'
    db=tmp_path/'synthetic.sqlite'
    with sqlite3.connect(db) as connection:
        connection.execute(schema)
        values=['a'*64,'2024-06-01','AA','123','AAA','BBB',900,1100,9,100.,120.,1,'2024-04',100,200,300,.2,.3,.4,.2,.3,.4,.5]
        connection.execute('INSERT INTO predictions VALUES ('+','.join('?' for _ in values)+')',values)
    results=tmp_path/'m3'; results.mkdir()
    (results/'metrics.json').write_text(json.dumps({'version':'synthetic','selection':{'recommended_model':'B3','selected':{'B3':{'validation':{'threshold':.4}}}}}))
    client=TestClient(create_app(predictions=db,results_dir=results))
    response=client.get('/api/risk/flight/'+'a'*64).json()
    assert 'label' not in response and 'actual_delayed' not in response
    assert response['predicted_delayed'] and response['score']==.5
    assert client.get('/api/risk/flight/'+'a'*64+'?reveal=true').json()['actual_delayed']
    assert client.get('/api/risk/flight/'+'b'*64).status_code==404
    assert client.get('/api/risk/flight/invalid').status_code==422
    assert client.get('/api/risk/flights?origin=AAA&dest=BBB&carrier=AA&date=2024-06-31').status_code==422
    assert client.get('/api/risk/options?origin=AAA').json()['destinations']==['BBB']
    assert len(client.get('/api/risk/flights?origin=AAA&dest=BBB&carrier=AA&date=2024-06-01').json()['flights'])==1
