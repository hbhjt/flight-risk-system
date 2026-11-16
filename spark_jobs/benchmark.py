"""Same cleaned records, explicit schema, identical SQL, alternating uncached reads."""
import json, time, hashlib, statistics
from datetime import datetime, timezone
from pathlib import Path
from pyspark.sql import SparkSession, functions as F

spark = SparkSession.builder.appName('FlightRisk-FormatBenchmark').config('spark.sql.shuffle.partitions','4').config('spark.sql.adaptive.enabled','false').getOrCreate()
spark.sparkContext.setLogLevel('WARN')
base='hdfs://127.0.0.1:19000/flight-risk'
try:
    frames=[spark.read.parquet(f'{base}/runs/2024-{i:02}/silver') for i in range(1,7)]
    frame=frames[0]
    for other in frames[1:]: frame=frame.unionByName(other)
    cleaned=frame.where("disposition != 'invalid_key_or_status'").select('month','Reporting_Airline','Origin',F.col('arrival_valid').cast('integer').alias('eligible'),F.col('delayed').cast('integer').alias('delayed'))
    n=cleaned.count()
    root=base+'/benchmark-v1'
    for fmt in ['csv','parquet']:
        writer=cleaned.repartition(4).write.mode('overwrite')
        if fmt=='csv': writer=writer.option('header',True).option('nullValue','__NULL__')
        writer.format(fmt).save(root+'/'+fmt)
    records=[];reference=None
    for round_id in range(3):
        for fmt in (['csv','parquet'] if round_id%2==0 else ['parquet','csv']):
            spark.catalog.clearCache()
            start=time.perf_counter()
            reader=spark.read.schema(cleaned.schema)
            if fmt=='csv': reader=reader.option('header',True).option('nullValue','__NULL__').option('mode','FAILFAST')
            data=reader.format(fmt).load(root+'/'+fmt)
            rows=data.groupBy('month','Reporting_Airline','Origin').agg(F.count('*').alias('planned'),F.sum('eligible').alias('eligible'),F.sum('delayed').alias('delayed')).collect()
            elapsed=time.perf_counter()-start
            canonical=sorted([list(row) for row in rows])
            digest=hashlib.sha256(json.dumps(canonical,separators=(',',':')).encode()).hexdigest()
            if reference is None: reference=digest
            if digest!=reference or sum(row[3] for row in canonical)!=n: raise ValueError('CSV/Parquet aggregation mismatch')
            records.append({'round':round_id+1,'format':fmt,'seconds':elapsed,'result_sha256':digest,'groups':len(rows),'records':n})
            print(json.dumps(records[-1]),flush=True)
    sizes={}
    fs=spark._jvm.org.apache.hadoop.fs.FileSystem.get(spark._jsc.hadoopConfiguration())
    for fmt in ['csv','parquet']:
        summary=fs.getContentSummary(spark._jvm.org.apache.hadoop.fs.Path(root+'/'+fmt))
        sizes[fmt]={'bytes':summary.getLength(),'files':summary.getFileCount()}
    result={'finished_at_utc':datetime.now(timezone.utc).isoformat(),'records':n,'repetitions':3,'runs':records,'storage':sizes,'medians':{fmt:statistics.median(r['seconds'] for r in records if r['format']==fmt) for fmt in ['csv','parquet']},'consistent':True,'result_sha256':reference,'spark_version':spark.version,'master':spark.sparkContext.master,'application_id':spark.sparkContext.applicationId,'partitions':4,'executor_cores':2,'executor_memory':'1g','driver_memory':'1g','columns':cleaned.columns,'sql':'GROUP BY month, Reporting_Airline, Origin; count(*), sum(eligible), sum(delayed)','cache_conditions':'Spark cache cleared each run; OS/HDFS caches not cleared. First observed reads reported, not claimed cold disk reads. Data conversion excluded from query timings.','scan_bytes':'Not instrumented; storage bytes are not claimed as actual scan bytes.'}
    out=Path('results/engineering/benchmark.json');out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2))
finally: spark.stop()
