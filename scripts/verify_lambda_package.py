"""Smoke-test the actual ZIP in Linux Lambda runtime, without AWS or a DB."""
import importlib.util
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build_lambda", ROOT / "scripts/build_lambda.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)

SMOKE = r'''
import json, os, sys, time, zipfile
from unittest.mock import patch
started = time.perf_counter()
with zipfile.ZipFile('/artifact/backend.zip') as archive:
    names = archive.namelist()
    assert not any(n.endswith(('.env', '.db', '.sqlite', '.sqlite3', '.pyc')) or '/tests/' in n for n in names)
    assert 'lambda_handler.py' in names and 'lambda_jobs.py' in names
    archive.extractall('/tmp/task')
sys.path.insert(0, '/tmp/task')
os.chdir('/tmp/task')
os.environ.update(APP_ENV='production', DB_POOLING='null', DB_PASSWORD='synthetic:password\\value',
    DATABASE_URL='postgresql+psycopg://campusshiftapp@unused.example.invalid/campusshift?sslmode=verify-full&sslrootcert=/tmp/task/certs/rds-us-east-2.pem',
    JWT_SECRET='synthetic-test-key-' * 4, CORS_ORIGINS='')
import lambda_handler, lambda_jobs, psycopg, argon2
from sqlalchemy.pool import NullPool
event = {'version':'2.0','routeKey':'$default','rawPath':'/api/health','rawQueryString':'','headers':{'host':'test.execute-api.us-east-2.amazonaws.com'},
 'requestContext':{'stage':'$default','http':{'method':'GET','path':'/api/health','sourceIp':'127.0.0.1','protocol':'HTTP/1.1'}},'body':'','isBase64Encoded':False}
with patch.object(psycopg.Connection, 'connect', side_effect=AssertionError('health must not open DB')):
    first = lambda_handler.handler(event, None)
    cold_ms = int((time.perf_counter()-started)*1000)
    adapter = lambda_handler.adapter()
    warm_start = time.perf_counter()
    second = lambda_handler.handler(event, None)
    warm_ms = int((time.perf_counter()-warm_start)*1000)
    assert adapter is lambda_handler.adapter()
    assert first['statusCode'] == second['statusCode'] == 200
    assert json.loads(first['body'])['status'] == 'healthy'
from main import app
assert isinstance(app.state.engine.pool, NullPool)
assert os.stat(os.environ['PGPASSFILE']).st_mode & 0o777 == 0o600
assert os.stat(os.path.dirname(os.environ['PGPASSFILE'])).st_mode & 0o777 == 0o700
secret = os.environ['DB_PASSWORD'].replace('\\','\\\\').replace(':','\\:')
assert open(os.environ['PGPASSFILE']).read().endswith(secret+'\n')
from datetime import date
from scheduler.engine import Student, Window, Requirement, generate
students = tuple(Student(i, 1, 1200, frozenset(range(1,6)), tuple(Window(d,540,1020) for d in range(7))) for i in range(1,51))
requirements = tuple(Requirement(1+d*5+loc,1,loc,d,540,1020,2) for d in range(7) for loc in range(1,6))
benchmark_start = time.perf_counter()
schedule = generate(1,date(2026,11,16),students,requirements)
scheduling_ms = int((time.perf_counter()-benchmark_start)*1000)
assert schedule.summary['coverage_percent'] == 100
print(json.dumps({'linux_zip_import':'passed','cold_local_ms':cold_ms,'warm_local_ms':warm_ms,'scheduling_50_students_35_requirements_ms':scheduling_ms,'coverage_percent':100,'db_connections_for_health':0,'passfile_mode':'0600','note':'Local Docker timings; AWS cold start/VPC/Aurora latency untested'}))
'''


if __name__ == "__main__":
    subprocess.run(["docker", "run", "--rm", "--network", "none", "--platform", "linux/amd64",
                    "--entrypoint", "python", "--mount", f"type=bind,source={ROOT / '.local/serverless'},target=/artifact,readonly",
                    builder.IMAGE, "-c", SMOKE], check=True)
