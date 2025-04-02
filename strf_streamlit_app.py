
import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.patches as patches
import base64
from io import BytesIO
import random

st.set_page_config(page_title="STRF Scheduler", layout="centered")
st.title("STRF Scheduler Simulator (Streamlit)")

with st.sidebar:
    st.header("Configuration")
    num_jobs = st.slider("Number of Jobs", 1, 10, 3)
    num_cpus = st.slider("Number of CPUs", 1, 5, 2)
    chunk_unit = st.selectbox("Chunk Time Unit", [1, 1.5, 2, 2.5, 3, 3.5, 4.5, 5])

    if st.button("Randomize"):
        arrivals = [random.randint(1, 10) for _ in range(num_jobs)]
        bursts = [random.choice([1, 1.5, 2, 2.5, 3, 3.5, 4.5, 5]) for _ in range(num_jobs)]
    else:
        arrivals = [st.number_input(f"Arrival Time for J{i+1}", value=float(i+1), key=f"a{i}") for i in range(num_jobs)]
        bursts = [st.number_input(f"Burst Time for J{i+1}", value=2.0, key=f"b{i}") for i in range(num_jobs)]

if st.button("Run Scheduler"):
    processes = [{'id': f'J{i+1}', 'arrival_time': arrivals[i], 'burst_time': bursts[i]} for i in range(num_jobs)]
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
            future_times = [t for t in busy_until.values() if t > current_time] + \
                           [arrival_time[j] for j in arrival_time if arrival_time[j] > current_time and remaining_time[j] > 0]
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

        future_times = [t for t in busy_until.values() if t > current_time] + \
                       [arrival_time[j] for j in arrival_time if arrival_time[j] > current_time and remaining_time[j] > 0]
        current_time = min(future_times) if future_times else current_time + 0.1

    for p in processes:
        p['start_time'] = start_time[p['id']]
        p['end_time'] = end_time[p['id']]
        p['turnaround_time'] = p['end_time'] - p['arrival_time']

    st.subheader("Job Summary Table")
    st.table([{**p} for p in processes])

    avg_tat = sum(p['turnaround_time'] for p in processes) / len(processes)
    st.success(f"Average Turnaround Time: {avg_tat:.2f}")

    # Gantt Chart
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
    st.pyplot(fig)
