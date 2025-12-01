"""Circuit breaker event listeners.

Available listeners:
    - LogListener: Logs state transitions (always available, works with sync/async)
    - PrometheusListener: Exports metrics to Prometheus (requires: pip install fluxgate[prometheus], works with sync/async)
    - SlackListener / AsyncSlackListener: Sends alerts to Slack (requires: pip install fluxgate[slack])

Usage:
    from fluxgate.listeners.log import LogListener
    from fluxgate.listeners.prometheus import PrometheusListener
    from fluxgate.listeners.slack import SlackListener, AsyncSlackListener
"""
