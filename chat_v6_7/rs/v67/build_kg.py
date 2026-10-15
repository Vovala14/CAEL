# Wikidata truthy (CC0) filtered lines -> integer-ID store in DuckDB.
import duckdb,time
t0=time.time();db=duckdb.connect('kg67.duckdb');db.execute("SET memory_limit='9GB'; SET threads=6; SET preserve_insertion_order=false")
db.execute(r"""create or replace temp table raw as
 select cast(regexp_extract(l,'^Q(\d+) ',1) as INTEGER) s, regexp_extract(l,'^Q\d+ (\S+) ',1) p, regexp_extract(l,'^Q\d+ \S+ (.*)$',1) o
 from read_csv('wd/facts.txt',columns={'l':'VARCHAR'},sep=chr(1),quote='',escape='',header=false,auto_detect=false,strict_mode=false,ignore_errors=true)""")
print('raw',db.execute('select count(*) from raw').fetchone(),time.time()-t0,flush=True)
db.execute("""create or replace temp table bad as select distinct s from raw where p='P31' and o in ('Q13442814','Q4167836','Q4167410','Q11266439','Q17633526','Q7187','Q8054','Q15184295','Q19842659','Q13406463','Q17362920','Q22808320','Q67015883','Q30612')""")
db.execute(r"""create or replace table fact as select r.s,cast(substr(p,2) as INTEGER) p, case when o similar to 'Q[0-9]+' then cast(substr(o,2) as INTEGER) end oq, case when not (o similar to 'Q[0-9]+') then o end olit
 from raw r anti join bad b on r.s=b.s where p like 'P%' order by r.s""")
db.execute("create or replace table deg as select s q,count(*)::INTEGER n from fact group by s")
db.execute(r"""create or replace table lab as select lower(regexp_extract(o,'^"(.*)"@en$',1)) as name, s q, (p='A') as isalias from raw r semi join deg d on r.s=d.q where p in ('L','A') order by name""")
db.execute(r"""create or replace table lbl as select s q, regexp_extract(o,'^"(.*)"@en$',1) as name from raw r semi join deg d on r.s=d.q where p='L' order by q""")
db.execute(r"""create or replace table descr as select s q, regexp_extract(o,'^"(.*)"@en$',1) as d from raw r semi join deg d on r.s=d.q where p='D' order by q""")
for t in ['fact','deg','lab','lbl','descr']: print(t,db.execute(f'select count(*) from {t}').fetchone(),flush=True)
db.execute('drop table raw');db.execute('drop table bad');db.execute('checkpoint');print('done',time.time()-t0)
