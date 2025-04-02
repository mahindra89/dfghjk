import streamlit as st
from scheduler import run_strf_simulation, draw_gantt_with_queue

def main():
    st.title("Multi-CPU STRF Scheduler with User-Defined Chunks")

    num_jobs = st.number_input("Enter the number of jobs:", min_value=1, step=1, value=3)
    num_cpus = st.number_input("Enter the number of CPUs:", min_value=1, step=1, value=2)
    chunk_unit = st.number_input("Enter the time unit to break each job into (e.g., 0.5, 1.0, 2.0):", 
                                 min_value=0.1, step=0.1, value=1.0)

    processes = []
    for i in range(num_jobs):
        st.subheader(f"Job J{i+1}")
        arrival = st.number_input(f"Enter arrival time for Job J{i+1}:", min_value=0.0, step=0.1, value=0.0, key=f"arrival_{i}")
        burst = st.number_input(f"Enter burst time for Job J{i+1}:", min_value=0.1, step=0.1, value=1.0, key=f"burst_{i}")
        processes.append({'id': f'J{i+1}', 'arrival_time': arrival, 'burst_time': burst})

    if st.button("Run Simulation"):
        gantt_data, queue_snapshots, processes_with_results, avg_turnaround = run_strf_simulation(
            processes, num_cpus, chunk_unit
        )

        st.subheader("Simulation Results")
        st.write(f"{'#Job':<5} {'Arrival':<8} {'Burst':<6} {'Start':<6} {'End':<6} {'Turnaround':<10}")
        for p in processes_with_results:
            st.write(f"{p['id']:<5} {p['arrival_time']:<8} {p['burst_time']:<6} {p['start_time']:<6.1f} {p['end_time']:<6.1f} {p['turnaround_time']:<10.1f}")
        st.write(f"\nAverage Turnaround Time: {avg_turnaround:.2f}")

        st.subheader("Gantt Chart")
        fig = draw_gantt_with_queue(gantt_data, queue_snapshots, num_cpus, processes)
        if fig is None:
            st.error("Failed to generate Gantt chart.")
        else:
            st.pyplot(fig)

if __name__ == "__main__":
    main()
