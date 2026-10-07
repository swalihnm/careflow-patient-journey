import os

os.environ.setdefault("CAREFLOW_DB_DSN", "postgresql://careflow:careflow@localhost:5544/careflow")
os.environ.setdefault("CAREFLOW_FHIR_BASE_URL", "http://localhost:8210/fhir")
