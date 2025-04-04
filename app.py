from flask import Flask, render_template, request
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.colors as mcolors  # Add this import
import io
import base64

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/schedule', methods=['POST'])
def schedule():
    num_jobs = int(request.form['num_jobs'])
    num_cpus = int(request.form['num_cpus'])
    chunk_unit = float(request.form['chunk_unit'])
    
    processes = []
    for i in range(num_jobs):
        arrival = float(request.form[f'arrival_{i}'])
        burst = float(request.form[f'burst_{i}'])
        processes.append({'id': f'J{i+1}', 'arrival_time': arrival, 'burst_time': burst})
    
    # Setup state
    arrival_time = {p['id']: p['arrival_time'] for p in processes}
    burst_time = {p['id']: p['burst_time'] for p in processes}
    remaining_time = {p['id']: p['burst_time'] for p in processes}
    start_time = {}
    end_time = {}
    job_chunks = {}
    
    # Break jobs into user-defined chunks
    for job_id, total_time in burst_time.items():
        chunks = []
        remaining = total_time
        while remaining > 0:
            chunk = min(chunk_unit, remaining)
            chunks.append(chunk)
            remaining -= chunk
        job_chunks[job_id] = chunks
    
    # CPU setup
    cpu_names = [f"CPU{i+1}" for i in range(num_cpus)]
    busy_until = {cpu: 0 for cpu in cpu_names}
    current_jobs = {cpu: None for cpu in cpu_names}
    busy_jobs = set()
    
    # Simulation state
    gantt_data = []
    queue_snapshots = []
    current_time = 0
    jobs_completed = 0
    
    # Capture queue state at each scheduling point
    def capture_queue_state(time, available_jobs):
        active_jobs = [j for j in available_jobs if remaining_time[j] > 0]
        queue = sorted(active_jobs, key=lambda job_id: (remaining_time[job_id], arrival_time[job_id]))
        job_info = [(job, round(remaining_time[job], 1)) for job in queue]
        if job_info:
            queue_snapshots.append((time, job_info))
    
    # Initial queue
    initial_available_jobs = [p['id'] for p in processes if p['arrival_time'] <= current_time]
    capture_queue_state(current_time, initial_available_jobs)
    
    # Simulation loop
    while jobs_completed < len(processes):
        next_events = []
    
        for cpu, time in busy_until.items():
            if time <= current_time:
                next_events.append((current_time, "CPU_AVAILABLE", cpu))
    
        for job_id, time in arrival_time.items():
            if time > current_time and remaining_time[job_id] > 0:
                next_events.append((time, "JOB_ARRIVAL", job_id))
    
        if not next_events:
            future_times = [t for _, t in busy_until.items() if t > current_time] + \
                           [t for j, t in arrival_time.items() if t > current_time and remaining_time[j] > 0]
            if future_times:
                current_time = min(future_times)
            continue
    
        next_events.sort(key=lambda x: (x[0], cpu_names.index(x[2]) if x[1] == "CPU_AVAILABLE" else num_cpus + 1))
    
        for cpu, busy_time in busy_until.items():
            if busy_time == current_time and current_jobs[cpu] is not None:
                job_id = current_jobs[cpu]
                if job_id in busy_jobs:
                    busy_jobs.remove(job_id)
                current_jobs[cpu] = None
    
        available_cpus = [cpu for cpu in cpu_names if busy_until[cpu] <= current_time and current_jobs[cpu] is None]
        available_jobs = [job_id for job_id in remaining_time
                          if remaining_time[job_id] > 0 and arrival_time[job_id] <= current_time and job_id not in busy_jobs]
    
        if available_cpus and available_jobs:
            capture_queue_state(current_time, available_jobs)
    
        if not available_jobs or not available_cpus:
            future_times = [busy_until[cpu] for cpu in busy_until if busy_until[cpu] > current_time] + \
                           [arrival_time[j] for j in arrival_time if arrival_time[j] > current_time and remaining_time[j] > 0]
            if future_times:
                current_time = min(future_times)
            continue
    
        available_jobs.sort(key=lambda job_id: (remaining_time[job_id], arrival_time[job_id]))
    
        for cpu in available_cpus:
            if not available_jobs:
                break
    
            selected_job = available_jobs.pop(0)
            if selected_job not in start_time:
                start_time[selected_job] = current_time
    
            chunk_size = job_chunks[selected_job].pop(0)
            busy_jobs.add(selected_job)
            current_jobs[cpu] = selected_job
    
            remaining_time[selected_job] -= chunk_size
            busy_until[cpu] = current_time + chunk_size
            gantt_data.append((current_time, cpu, selected_job, chunk_size))
    
            if abs(remaining_time[selected_job]) < 0.001:
                end_time[selected_job] = current_time + chunk_size
                jobs_completed += 1
    
        next_time_events = [busy_until[cpu] for cpu in busy_until if busy_until[cpu] > current_time] + \
                           [arrival_time[j] for j in arrival_time if arrival_time[j] > current_time and remaining_time[j] > 0]
    
        if next_time_events:
            current_time = min(next_time_events)
        else:
            current_time += 0.1
    
    # Output results
    for p in processes:
        p['start_time'] = start_time[p['id']]
        p['end_time'] = end_time[p['id']]
        p['turnaround_time'] = p['end_time'] - p['arrival_time']
    
    avg_turnaround = sum(p['turnaround_time'] for p in processes) / len(processes)
    
    # Generate Gantt chart
    fig, ax = plt.subplots(figsize=(14, 6))
    
    # Generate dynamic colors for each job (Matplotlib 3.7+ safe)
    cmap = plt.colormaps.get_cmap('tab20')
    colors = {f'J{i+1}': mcolors.to_hex(cmap(i / max(len(processes), 1))) for i in range(len(processes))}
    
    cpu_ypos = {cpu: num_cpus - idx for idx, cpu in enumerate(cpu_names)}
    
    for start_time, cpu, job, duration in gantt_data:
        y_pos = cpu_ypos[cpu]
        ax.barh(y=y_pos, width=duration, left=start_time,
                color=colors[job], edgecolor='black')
        ax.text(start_time + duration / 2, y_pos, job,
                ha='center', va='center', color='white', fontsize=9)
    
    for t in range(int(max(end_time.values())) + 1):
        ax.axvline(x=t, color='black', linestyle='--', alpha=0.3)
    
    ax.set_yticks(list(cpu_ypos.values()))
    ax.set_yticklabels(cpu_ypos.keys())
    ax.set_xlim(0, max(end_time.values()) + 0.5)
    ax.set_xlabel("Time (seconds)")
    ax.set_title("Multi-CPU STRF with User-Defined Chunks and Dynamic Colors")
    
    # Queue visualization
    queue_y_base = -1
    for time, job_queue in queue_snapshots:
        for i, (job_id, remaining) in enumerate(job_queue):
            box_y = queue_y_base - i * 0.6
            rect = patches.Rectangle((time - 0.25, box_y - 0.25), 0.5, 0.5,
                                     linewidth=1, edgecolor='black', facecolor='white', fill=True)
            ax.add_patch(rect)
            ax.text(time, box_y, f"{job_id} = {remaining}", ha='center', va='center', fontsize=7)
    
    if queue_snapshots:
        max_len = max(len(q[1]) for q in queue_snapshots)
        min_y = queue_y_base - max_len * 0.6 - 0.5
        ax.set_ylim(min_y, max(cpu_ypos.values()) + 1)
    
    plt.tight_layout()
    plt.grid(axis='x')
    
    # Save the plot to a string buffer
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    image_base64 = base64.b64encode(buf.read()).decode('utf-8')
    buf.close()
    
    return render_template('result.html', image_base64=image_base64, avg_turnaround=avg_turnaround)

if __name__ == '__main__':
    app.run(debug=True)
