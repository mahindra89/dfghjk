
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.colors as mcolors
import base64
from io import BytesIO

# Assume variables set from JS: num_jobs, num_cpus, chunk_unit, job_data
processes = []
for i in range(num_jobs):
    arrival, burst = job_data[i]
    processes.append({'id': f'J{i+1}', 'arrival_time': arrival, 'burst_time': burst})

arrival_time = {p['id']: p['arrival_time'] for p in processes}
burst_time = {p['id']: p['burst_time'] for p in processes}
remaining_time = {p['id']: p['burst_time'] for p in processes}
start_time = {}
end_time = {}
job_chunks = {}

for job_id, total_time in burst_time.items():
    chunks = []
    remaining = total_time
    while remaining > 0:
        chunk = min(chunk_unit, remaining)
        chunks.append(chunk)
        remaining -= chunk
    job_chunks[job_id] = chunks

cpu_names = [f"CPU{i+1}" for i in range(num_cpus)]
busy_until = {cpu: 0 for cpu in cpu_names}
current_jobs = {cpu: None for cpu in cpu_names}
busy_jobs = set()

gantt_data = []
current_time = 0
jobs_completed = 0

while jobs_completed < len(processes):
    for cpu in cpu_names:
        if busy_until[cpu] <= current_time and current_jobs[cpu]:
            busy_jobs.discard(current_jobs[cpu])
            current_jobs[cpu] = None

    available_cpus = [cpu for cpu in cpu_names if busy_until[cpu] <= current_time and current_jobs[cpu] is None]
    available_jobs = [j for j in remaining_time if remaining_time[j] > 0 and arrival_time[j] <= current_time and j not in busy_jobs]

    if not available_cpus or not available_jobs:
        future_times = [t for t in busy_until.values() if t > current_time] +                        [arrival_time[j] for j in arrival_time if arrival_time[j] > current_time and remaining_time[j] > 0]
        current_time = min(future_times) if future_times else current_time + 0.1
        continue

    available_jobs.sort(key=lambda j: (remaining_time[j], arrival_time[j]))

    for cpu in available_cpus:
        if not available_jobs:
            break
        job = available_jobs.pop(0)
        if job not in start_time:
            start_time[job] = current_time
        chunk_size = job_chunks[job].pop(0)
        remaining_time[job] -= chunk_size
        current_jobs[cpu] = job
        busy_jobs.add(job)
        busy_until[cpu] = current_time + chunk_size
        gantt_data.append((current_time, cpu, job, chunk_size))
        if abs(remaining_time[job]) < 0.001:
            end_time[job] = current_time + chunk_size
            jobs_completed += 1

    future_times = [t for t in busy_until.values() if t > current_time] +                    [arrival_time[j] for j in arrival_time if arrival_time[j] > current_time and remaining_time[j] > 0]
    current_time = min(future_times) if future_times else current_time + 0.1

for p in processes:
    p['start_time'] = start_time[p['id']]
    p['end_time'] = end_time[p['id']]
    p['turnaround_time'] = p['end_time'] - p['arrival_time']

summary = f"{'#Job':<5} {'Arrival':<8} {'Burst':<6} {'Start':<6} {'End':<6} {'Turnaround':<10}\n"
for p in processes:
    summary += f"{p['id']:<5} {p['arrival_time']:<8} {p['burst_time']:<6} {p['start_time']:<6.1f} {p['end_time']:<6.1f} {p['turnaround_time']:<10.1f}\n"
summary += f"\nAverage Turnaround Time: {sum(p['turnaround_time'] for p in processes)/len(processes):.2f}"
import sys
import io
sys.stdout = io.StringIO()
print(summary)

fig, ax = plt.subplots(figsize=(10, 5))
cmap = plt.colormaps.get_cmap('tab10')
colors = {f'J{i+1}': cmap(i % 10) for i in range(len(processes))}
y_pos = {cpu: i for i, cpu in enumerate(cpu_names)}

for start, cpu, job, dur in gantt_data:
    y = y_pos[cpu]
    ax.barh(y, dur, left=start, color=colors[job], edgecolor='black')
    ax.text(start + dur / 2, y, job, ha='center', va='center', color='white', fontsize=8)

ax.set_yticks(list(y_pos.values()))
ax.set_yticklabels(cpu_names)
ax.set_xlabel("Time")
ax.set_title("STRF Scheduling Gantt Chart")
plt.tight_layout()

buf = BytesIO()
plt.savefig(buf, format='png')
buf.seek(0)
img_base64 = base64.b64encode(buf.read()).decode('utf-8')
from js import document
document.getElementById("chart").innerHTML = f"<img src='data:image/png;base64,{img_base64}' />"
