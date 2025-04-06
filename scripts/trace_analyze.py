#!/usr/bin/env python3
"""
Trace Analysis Tool

This script helps analyze traces from Jaeger to identify performance issues
and understand request flow across services.

Usage:
  python trace_analyze.py [options]

Options:
  --trace-id ID        Analyze a specific trace by ID
  --service NAME       Filter traces by service name
  --operation NAME     Filter traces by operation name
  --tag KEY=VALUE      Filter traces by tag (can be used multiple times)
  --limit N            Limit number of traces to retrieve (default: 20)
  --since HOURS        Only show traces from the last N hours (default: 24)
  --format FORMAT      Output format (text, json) (default: text)
  --sort FIELD         Sort by field (duration, spans, services) (default: duration)
  --top N              Show only the top N traces (default: all)
  --verbose            Show detailed information
  --output FILE        Write output to file
"""

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import time
from collections import defaultdict

def query_jaeger(args):
    """Query traces from Jaeger API"""
    # Build query parameters
    params = []
    
    if args.service:
        params.append(f"service={args.service}")
    
    if args.operation:
        params.append(f"operation={args.operation}")
    
    if args.tags:
        for tag in args.tags:
            key, value = tag.split('=', 1)
            params.append(f"tags=%7B%22{key}%22%3A%22{value}%22%7D")
    
    if args.since:
        # Calculate start time in microseconds
        lookback = int(time.time() * 1000000) - (args.since * 3600 * 1000000)
        params.append(f"start={lookback}")
    
    params.append(f"limit={args.limit}")
    
    # If specific trace ID provided, use direct API
    if args.trace_id:
        url = f"http://localhost:16686/api/traces/{args.trace_id}"
    else:
        url = f"http://localhost:16686/api/traces?{'&'.join(params)}"
    
    try:
        # Run curl to fetch trace data
        result = subprocess.run(["curl", "-s", url], capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    except (subprocess.SubprocessError, json.JSONDecodeError) as e:
        print(f"Error retrieving traces: {e}")
        sys.exit(1)

def analyze_trace(trace):
    """Extract key insights from a trace"""
    spans = trace.get("spans", [])
    processes = trace.get("processes", {})
    
    # Basic metrics
    trace_id = trace.get("traceID", "Unknown")
    span_count = len(spans)
    
    # Duration analysis
    durations = [span.get("duration", 0) for span in spans]
    total_duration = max(durations) if durations else 0  # Microseconds
    
    # Service stats
    service_spans = defaultdict(list)
    for span in spans:
        process_id = span.get("processID")
        if process_id and process_id in processes:
            service_name = processes[process_id].get("serviceName", "unknown")
            service_spans[service_name].append(span)
    
    service_count = len(service_spans)
    
    # Calculate service time contributions
    service_durations = {}
    for service, svc_spans in service_spans.items():
        # This is a simplification - in reality spans can overlap
        service_durations[service] = sum(span.get("duration", 0) for span in svc_spans)
    
    # Find critical path
    # This is a simplified approach - proper critical path analysis is more complex
    critical_path = []
    if spans:
        # Sort spans by start time
        sorted_spans = sorted(spans, key=lambda s: s.get("startTime", 0))
        
        # Simple greedy algorithm - not accurate for complex traces
        current_end = 0
        for span in sorted_spans:
            start = span.get("startTime", 0)
            end = start + span.get("duration", 0)
            
            if start >= current_end:
                # Get operation name and service
                operation = span.get("operationName", "unknown")
                process_id = span.get("processID")
                service = "unknown"
                if process_id and process_id in processes:
                    service = processes[process_id].get("serviceName", "unknown")
                
                critical_path.append({
                    "service": service,
                    "operation": operation,
                    "duration": span.get("duration", 0),
                    "start": start,
                    "end": end
                })
                current_end = end
    
    # Find errors
    errors = []
    for span in spans:
        has_error = False
        for tag in span.get("tags", []):
            if tag.get("key") == "error" and tag.get("value") == "true":
                has_error = True
                break
        
        if has_error:
            process_id = span.get("processID")
            service = "unknown"
            if process_id and process_id in processes:
                service = processes[process_id].get("serviceName", "unknown")
            
            errors.append({
                "service": service,
                "operation": span.get("operationName", "unknown"),
                "duration": span.get("duration", 0),
                "logs": span.get("logs", [])
            })
    
    # Identify long operations
    threshold_ms = 100  # Consider spans over 100ms as "long"
    long_operations = []
    for span in spans:
        duration_ms = span.get("duration", 0) / 1000
        if duration_ms > threshold_ms:
            process_id = span.get("processID")
            service = "unknown"
            if process_id and process_id in processes:
                service = processes[process_id].get("serviceName", "unknown")
            
            long_operations.append({
                "service": service,
                "operation": span.get("operationName", "unknown"),
                "duration_ms": duration_ms
            })
    
    # Sort long operations by duration
    long_operations.sort(key=lambda x: x["duration_ms"], reverse=True)
    
    return {
        "trace_id": trace_id,
        "span_count": span_count,
        "total_duration_ms": total_duration / 1000,  # Convert to milliseconds
        "services": list(service_spans.keys()),
        "service_count": service_count,
        "service_durations": {svc: dur / 1000 for svc, dur in service_durations.items()},  # ms
        "errors": errors,
        "critical_path": critical_path,
        "long_operations": long_operations
    }

def print_trace_summary(analysis, verbose=False):
    """Print a summary of the trace analysis"""
    print(f"Trace ID: {analysis['trace_id']}")
    print(f"Duration: {analysis['total_duration_ms']:.2f} ms")
    print(f"Spans: {analysis['span_count']}")
    print(f"Services: {', '.join(analysis['services'])}")
    
    print("\nService Time Contribution:")
    total_ms = analysis['total_duration_ms']
    for service, duration_ms in sorted(analysis['service_durations'].items(), key=lambda x: x[1], reverse=True):
        percentage = (duration_ms / total_ms) * 100 if total_ms > 0 else 0
        print(f"  {service}: {duration_ms:.2f} ms ({percentage:.1f}%)")
    
    if analysis['errors']:
        print("\nErrors:")
        for error in analysis['errors']:
            print(f"  {error['service']} - {error['operation']} ({error['duration'] / 1000:.2f} ms)")
            if verbose and error['logs']:
                for log in error['logs']:
                    print(f"    {log.get('timestamp', 'unknown')}: {log.get('fields', [])}")
    
    print("\nLong Operations (>100ms):")
    for op in analysis['long_operations'][:5]:  # Show top 5 by default
        print(f"  {op['service']} - {op['operation']}: {op['duration_ms']:.2f} ms")
    
    if verbose:
        print("\nCritical Path:")
        for i, span in enumerate(analysis['critical_path']):
            print(f"  {i+1}. {span['service']} - {span['operation']}: {span['duration'] / 1000:.2f} ms")
    
    # Add URL to view in Jaeger
    print(f"\nView in Jaeger: http://localhost:16686/trace/{analysis['trace_id']}")

def main():
    parser = argparse.ArgumentParser(description="Analyze traces from Jaeger")
    parser.add_argument("--trace-id", help="Analyze a specific trace by ID")
    parser.add_argument("--service", help="Filter traces by service name")
    parser.add_argument("--operation", help="Filter traces by operation name")
    parser.add_argument("--tags", action="append", help="Filter traces by tag (format: key=value)")
    parser.add_argument("--limit", type=int, default=20, help="Limit number of traces to retrieve")
    parser.add_argument("--since", type=int, default=24, help="Only show traces from the last N hours")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format")
    parser.add_argument("--sort", choices=["duration", "spans", "services"], default="duration", 
                       help="Sort traces by field")
    parser.add_argument("--top", type=int, help="Show only the top N traces")
    parser.add_argument("--verbose", action="store_true", help="Show detailed information")
    parser.add_argument("--output", help="Write output to file")
    
    args = parser.parse_args()
    
    # Check if Jaeger is running
    try:
        subprocess.run(["curl", "-s", "http://localhost:16686/api/services"], 
                      capture_output=True, check=True)
    except subprocess.SubprocessError:
        print("Error: Cannot connect to Jaeger. Make sure it's running on http://localhost:16686")
        sys.exit(1)
    
    # Get traces from Jaeger
    traces_data = query_jaeger(args)
    
    if args.trace_id:
        # Single trace mode
        if not traces_data or not traces_data.get("data"):
            print(f"No trace found with ID: {args.trace_id}")
            sys.exit(1)
        
        trace = traces_data["data"][0]
        analysis = analyze_trace(trace)
        
        if args.format == "json":
            if args.output:
                with open(args.output, 'w') as f:
                    json.dump(analysis, f, indent=2)
            else:
                print(json.dumps(analysis, indent=2))
        else:
            print_trace_summary(analysis, args.verbose)
    
    else:
        # Multiple traces mode
        if not traces_data or not traces_data.get("data"):
            print("No traces found matching the criteria.")
            sys.exit(0)
        
        traces = traces_data["data"]
        
        # Analyze all traces
        analyses = [analyze_trace(trace) for trace in traces]
        
        # Sort the analyses
        if args.sort == "duration":
            analyses.sort(key=lambda a: a["total_duration_ms"], reverse=True)
        elif args.sort == "spans":
            analyses.sort(key=lambda a: a["span_count"], reverse=True)
        elif args.sort == "services":
            analyses.sort(key=lambda a: a["service_count"], reverse=True)
        
        # Apply top limit if specified
        if args.top:
            analyses = analyses[:args.top]
        
        if args.format == "json":
            if args.output:
                with open(args.output, 'w') as f:
                    json.dump(analyses, f, indent=2)
            else:
                print(json.dumps(analyses, indent=2))
        else:
            print(f"Found {len(analyses)} traces")
            for i, analysis in enumerate(analyses):
                print(f"\n--- Trace {i+1} ---")
                print_trace_summary(analysis, args.verbose)

if __name__ == "__main__":
    main()
