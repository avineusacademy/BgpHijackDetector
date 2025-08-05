from fastapi import FastAPI, BackgroundTasks, HTTPException
from datetime import datetime, timedelta
import uuid
import asyncio
import httpx

app = FastAPI()
RIPE_URL = "https://stat.ripe.net/data/bgp-updates/data.json"
jobs = {}  # job_id → {status, chunk_results: [], total_chunks, resource}

async def fetch_chunk(resource, start, end):
    params = {"resource": resource, "starttime": start, "endtime": end, "max_records": 1000}
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(RIPE_URL, params=params)
        resp.raise_for_status()
        return resp.json()

async def process_job(job_id: str, resource: str, starttime: str, endtime: str, chunk_hours=2):
    start = datetime.fromisoformat(starttime.rstrip("Z"))
    end = datetime.fromisoformat(endtime.rstrip("Z"))
    chunks = []
    cur = start
    while cur < end:
        nxt = min(end, cur + timedelta(hours=chunk_hours))
        chunks.append((cur.isoformat()+"Z", nxt.isoformat()+"Z"))
        cur = nxt

    jobs[job_id] = {
        "status": "pending",
        "chunk_results": [],
        "total_chunks": len(chunks),
        "resource": resource
    }

    for idx, (stt, edt) in enumerate(chunks):
        jobs[job_id]["status"] = f"processing_chunk_{idx+1}/{len(chunks)}"
        data = await fetch_chunk(resource, stt, edt)
        jobs[job_id]["chunk_results"].append({
            "start": stt,
            "end": edt,
            "data": data
        })

    jobs[job_id]["status"] = "completed"

@app.post("/api/bgp-historic-job")
async def create_job(resource: str, starttime: str, endtime: str, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    background_tasks.add_task(process_job, job_id, resource, starttime, endtime)
    return {"job_id": job_id}

@app.get("/api/bgp-historic-job/{job_id}")
async def get_job_status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
