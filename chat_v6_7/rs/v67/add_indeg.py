import duckdb;d=duckdb.connect('kg67.duckdb');d.execute("SET memory_limit='8GB'")
d.execute("create or replace table pop as select g.q, (g.n + coalesce(i.k,0))::INTEGER n from deg g left join (select oq q,count(*) k from fact where oq is not null and p<>31 and p<>279 group by oq) i on g.q=i.q order by g.q")
d.execute('checkpoint');print(d.execute('select * from pop where q in (935,937,142,230,1428,513,1748)').fetchall())
