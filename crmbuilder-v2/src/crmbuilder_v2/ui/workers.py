"""QThread worker pattern for off-thread HTTP calls.

Wired in slice C. Generic ``Worker`` QObject + ``run_worker(callable,
on_success, on_error)`` helper. Every HTTP call goes through a worker
so the UI thread never blocks on I/O.
"""
