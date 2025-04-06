#!/usr/bin/env python3
"""
SLO management extensions for the microservices CLI.
This module adds commands for monitoring and managing Service Level Objectives.
"""
import argparse
import time
import json
import sys
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any

# Try to import rich for better display
try:
    from rich.console import Console
    from rich.table import Table
    from rich.progress import Progress
    from rich.panel import Panel
    from rich.text import Text
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

# Initialize Rich console if available
if HAS_RICH:
    console = Console()

def print_info(message):
    """Print info message with nice formatting if Rich is available"""
    if HAS_RICH:
        console.print(f"[blue]{message}[/blue]")
    else:
        print(f"INFO: {message}")

def print_success(message):
    """Print success message with nice formatting if Rich is available"""
    if HAS_RICH:
        console.print(f"[green]✅ {message}[/green]")
    else:
        print(f"SUCCESS: {message}")
        
def print_error(message):
    """Print error message with nice formatting if Rich is available"""
    if HAS_RICH:
        console.print(f"[bold red]❌ {message}[/bold red]")
    else:
        print(f"ERROR: {message}")

def print_warning(message):
    """Print warning message with nice formatting if Rich is available"""
    if HAS_RICH:
        console.print(f"[yellow]⚠️ {message}[/yellow]")
    else:
        print(f"WARNING: {message}")

# SLO Definitions
SLO_DEFINITIONS = {
    'api_health': {
        'description': 'API Health endpoint latency',
        'target': 0.95,  # 95% of requests under target latency
        'latency_target': 0.1,  # 100ms
        'error_budget': 0.05,  # 5% error budget
        'windows': ['5m', '1h', '24h'],
        'endpoints': ['health_check', 'read_root']
    },
    'external_data': {
        'description': 'External data retrieval latency',
        'target': 0.90,  # 90% of requests under target latency
        'latency_target': 0.3,  # 300ms
        'error_budget': 0.10,  # 10% error budget
        'windows': ['5m', '1h', '24h'],
        'endpoints': ['get_external_data']
    },
    'data_access': {
        'description': 'Database access operations latency',
        'target': 0.95,  # 95% of requests under target latency
        'latency_target': 0.2,  # 200ms
        'error_budget': 0.05,  # 5% error budget
        'windows': ['5m', '1h', '24h'],
        'endpoints': ['read_users', 'read_items', 'create_user', 'create_item']
    }
}

def query_prometheus(query: str) -> Dict:
    """Execute a PromQL query against Prometheus"""
    try:
        response = requests.get(
            'http://localhost:9090/api/v1/query',
            params={'query': query}
        )
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print_error(f"Error querying Prometheus: {e}")
        return {"data": {"result": []}}

def get_slo_compliance(slo_name: str, window: str = "5m") -> Optional[float]:
    """Get the current compliance ratio for an SLO"""
    query = f'slo_compliance_ratio{{slo="{slo_name}", window="{window}"}}'
    result = query_prometheus(query)
    
    data = result.get('data', {}).get('result', [])
    if not data:
        return None
    
    # Extract the value from the first result
    return float(data[0]['value'][1])

def get_error_budget_remaining(slo_name: str, window: str = "5m") -> Optional[float]:
    """Get the remaining error budget for an SLO"""
    query = f'slo_error_budget_remaining{{slo="{slo_name}", window="{window}"}}'
    result = query_prometheus(query)
    
    data = result.get('data', {}).get('result', [])
    if not data:
        return None
    
    # Extract the value from the first result
    return float(data[0]['value'][1])

def get_latency_percentiles(slo_name: str) -> Dict[str, float]:
    """Get latency percentiles for an SLO"""
    percentiles = {}
    
    for percentile in [50, 90, 95, 99]:
        query = f'histogram_quantile({percentile/100}, sum(rate(slo_request_latency_seconds_bucket{{slo="{slo_name}"}}[5m])) by (le))'
        result = query_prometheus(query)
        
        data = result.get('data', {}).get('result', [])
        if data:
            percentiles[f"p{percentile}"] = float(data[0]['value'][1])
    
    return percentiles

def get_all_slo_status() -> Dict[str, Dict]:
    """Get status for all SLOs"""
    status = {}
    
    for slo_name in SLO_DEFINITIONS.keys():
        status[slo_name] = {
            "definition": SLO_DEFINITIONS[slo_name],
            "compliance": {},
            "budget_remaining": {},
            "latency": get_latency_percentiles(slo_name)
        }
        
        # Get compliance for each window
        for window in SLO_DEFINITIONS[slo_name]["windows"]:
            compliance = get_slo_compliance(slo_name, window)
            if compliance is not None:
                status[slo_name]["compliance"][window] = compliance
            
            budget = get_error_budget_remaining(slo_name, window)
            if budget is not None:
                status[slo_name]["budget_remaining"][window] = budget
    
    return status

def get_active_alerts() -> List[Dict]:
    """Get list of active SLO-related alerts"""
    query = 'ALERTS{severity=~"warning|critical", alertname=~".*Slo.*|.*Budget.*"}'
    result = query_prometheus(query)
    
    alerts = []
    for alert in result.get('data', {}).get('result', []):
        alerts.append({
            "name": alert['metric'].get('alertname', 'Unknown'),
            "severity": alert['metric'].get('severity', 'Unknown'),
            "slo": alert['metric'].get('slo', 'Unknown'),
            "state": "firing" if float(alert['value'][1]) == 1 else "resolved",
            "labels": alert['metric']
        })
    
    return alerts

def display_slo_status(args):
    """Display current SLO status"""
    if args.slo and args.slo not in SLO_DEFINITIONS:
        print_error(f"Unknown SLO: {args.slo}")
        print_info(f"Available SLOs: {', '.join(SLO_DEFINITIONS.keys())}")
        return
    
    # Get status for requested SLOs
    if args.slo:
        status = {args.slo: get_all_slo_status()[args.slo]}
    else:
        status = get_all_slo_status()
    
    if HAS_RICH:
        # Create a table for each SLO
        for slo_name, slo_status in status.items():
            table = Table(title=f"SLO: {slo_name} - {slo_status['definition']['description']}")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")
            table.add_column("Status", style="yellow")
            
            # Add target
            target = slo_status['definition']['target'] * 100
            table.add_row(
                "Target", 
                f"{target:.1f}% of requests under {slo_status['definition']['latency_target']*1000:.0f}ms",
                ""
            )
            
            # Add compliance for each window
            for window, compliance in slo_status['compliance'].items():
                compliance_pct = compliance * 100
                target_pct = slo_status['definition']['target'] * 100
                
                if compliance >= slo_status['definition']['target']:
                    status_text = "[green]✅ Meeting target[/green]"
                else:
                    status_text = f"[red]❌ Below target ({target_pct:.1f}%)[/red]"
                
                table.add_row(
                    f"Compliance ({window})",
                    f"{compliance_pct:.2f}%",
                    status_text
                )
            
            # Add budget remaining for each window
            for window, budget in slo_status['budget_remaining'].items():
                budget_pct = budget * 100
                
                if budget > 0.5:
                    status_text = "[green]✅ Healthy[/green]"
                elif budget > 0.2:
                    status_text = "[yellow]⚠️ Monitor[/yellow]"
                else:
                    status_text = "[red]❌ Critical[/red]"
                
                table.add_row(
                    f"Error Budget ({window})",
                    f"{budget_pct:.2f}% remaining",
                    status_text
                )
            
            # Add latency percentiles
            for percentile, value in slo_status['latency'].items():
                table.add_row(
                    f"Latency {percentile}",
                    f"{value*1000:.2f}ms",
                    ""
                )
            
            console.print(table)
            console.print("")
    else:
        # Plain text output
        for slo_name, slo_status in status.items():
            print(f"SLO: {slo_name} - {slo_status['definition']['description']}")
            print(f"Target: {slo_status['definition']['target']*100:.1f}% of requests under {slo_status['definition']['latency_target']*1000:.0f}ms")
            
            # Compliance
            for window, compliance in slo_status['compliance'].items():
                print(f"Compliance ({window}): {compliance*100:.2f}% (Target: {slo_status['definition']['target']*100:.1f}%)")
            
            # Budget
            for window, budget in slo_status['budget_remaining'].items():
                print(f"Error Budget ({window}): {budget*100:.2f}% remaining")
            
            # Latency
            for percentile, value in slo_status['latency'].items():
                print(f"Latency {percentile}: {value*1000:.2f}ms")
            
            print("")

def display_slo_alerts(args):
    """Display active SLO alerts"""
    alerts = get_active_alerts()
    
    if not alerts:
        print_info("No active SLO alerts")
        return
    
    if HAS_RICH:
        table = Table(title="Active SLO Alerts")
        table.add_column("Alert", style="cyan")
        table.add_column("SLO", style="blue")
        table.add_column("Severity", style="yellow")
        table.add_column("State", style="red")
        
        for alert in alerts:
            severity_style = "red" if alert['severity'] == "critical" else "yellow"
            state_style = "red" if alert['state'] == "firing" else "green"
            
            table.add_row(
                alert['name'],
                alert.get('slo', 'N/A'),
                f"[{severity_style}]{alert['severity']}[/{severity_style}]",
                f"[{state_style}]{alert['state']}[/{state_style}]"
            )
        
        console.print(table)
    else:
        print("Active SLO Alerts:")
        for alert in alerts:
            print(f"- {alert['name']} ({alert['severity']}) - {alert['state']}")

def run_slo_test(args):
    """Run a load test to verify SLO monitoring"""
    if not args.endpoint:
        print_error("Please specify an endpoint to test with --endpoint")
        return
    
    if not args.requests:
        args.requests = 100
    
    if not args.concurrency:
        args.concurrency = 5
    
    # Check if ab (ApacheBench) is installed
    try:
        import subprocess
        subprocess.run(["ab", "-h"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except Exception:
        print_error("Apache Bench (ab) is not installed or not in PATH")
        print_info("Install with: apt-get install apache2-utils")
        return
    
    # Construct the URL
    url = f"http://localhost:8000{args.endpoint}"
    
    print_info(f"Running load test against {url}")
    print_info(f"Requests: {args.requests}, Concurrency: {args.concurrency}")
    
    if HAS_RICH:
        with Progress() as progress:
            task = progress.add_task("[green]Running test...", total=1)
            
            # Run the load test
            result = subprocess.run(
                ["ab", "-n", str(args.requests), "-c", str(args.concurrency), url],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            progress.update(task, advance=1)
    else:
        # Run the load test
        print("Running test...")
        result = subprocess.run(
            ["ab", "-n", str(args.requests), "-c", str(args.concurrency), url],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
    
    # Parse the results
    if result.returncode != 0:
        print_error(f"Load test failed: {result.stderr}")
        return
    
    # Extract key metrics
    rps = None
    mean_time = None
    p95_time = None
    for line in result.stdout.splitlines():
        if "Requests per second" in line:
            rps = float(line.split(":")[1].strip().split()[0])
        elif "Time per request" in line and "mean, across all concurrent requests" not in line:
            mean_time = float(line.split(":")[1].strip().split()[0])
        elif "95%" in line:
            p95_time = float(line.strip().split()[1])
    
    if HAS_RICH:
        panel = Panel(
            f"[bold]Load Test Results[/bold]\n\n"
            f"Endpoint: {url}\n"
            f"Requests: {args.requests}, Concurrency: {args.concurrency}\n\n"
            f"Requests per second: {rps:.2f}\n"
            f"Mean time per request: {mean_time:.2f} ms\n"
            f"95th percentile: {p95_time:.2f} ms\n",
            title="Load Test Results",
            border_style="green"
        )
        console.print(panel)
    else:
        print("\nLoad Test Results:")
        print(f"Endpoint: {url}")
        print(f"Requests: {args.requests}, Concurrency: {args.concurrency}")
        print(f"Requests per second: {rps:.2f}")
        print(f"Mean time per request: {mean_time:.2f} ms")
        print(f"95th percentile: {p95_time:.2f} ms")
    
    # Wait a moment for metrics to be collected
    print_info("Waiting for metrics to be collected...")
    time.sleep(5)
    
    # Display SLO status
    affected_slo = None
    for slo_name, slo_def in SLO_DEFINITIONS.items():
        if any(endpoint == args.endpoint for endpoint in slo_def["endpoints"]):
            affected_slo = slo_name
            break
    
    if affected_slo:
        print_info(f"Checking SLO status for {affected_slo}...")
        args.slo = affected_slo
        display_slo_status(args)
    else:
        print_warning(f"Endpoint {args.endpoint} is not covered by any SLO")

def create_argparser():
    """Create a parser for SLO commands"""
    parser = argparse.ArgumentParser(description="SLO Management Tools")
    subparsers = parser.add_subparsers(dest="command", help="SLO command to execute")
    
    # SLO status command
    status_parser = subparsers.add_parser("status", help="Show SLO status")
    status_parser.add_argument("--slo", help="Show status for a specific SLO")
    status_parser.set_defaults(func=display_slo_status)
    
    # SLO alerts command
    alerts_parser = subparsers.add_parser("alerts", help="Show active SLO alerts")
    alerts_parser.set_defaults(func=display_slo_alerts)
    
    # SLO test command
    test_parser = subparsers.add_parser("test", help="Run a load test to verify SLO monitoring")
    test_parser.add_argument("--endpoint", help="API endpoint to test (e.g., /health)")
    test_parser.add_argument("--requests", type=int, help="Number of requests to send")
    test_parser.add_argument("--concurrency", type=int, help="Number of concurrent requests")
    test_parser.set_defaults(func=run_slo_test)
    
    return parser

def slo_command_handler(args):
    """Main entry point for SLO commands"""
    parser = create_argparser()
    
    # If no arguments, show help
    if not args:
        parser.print_help()
        return
    
    # Parse arguments
    args = parser.parse_args(args)
    
    # Execute the function for the specified command
    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    slo_command_handler(sys.argv[1:])
