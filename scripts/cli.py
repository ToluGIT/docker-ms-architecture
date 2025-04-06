#!/usr/bin/env python3
import argparse
import subprocess
import time
import sys
import os
from pathlib import Path
import json
import shutil
import datetime
import re

try:
    from rich.console import Console
    from rich.table import Table
    from rich.progress import Progress
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    print("Rich library not found. Install it for better display: pip install rich")

# Initialize Rich console if available
if HAS_RICH:
    console = Console()
else:
    console = None

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
COMPOSE_DEV = PROJECT_ROOT / "docker-compose.dev.yml"
COMPOSE_PROD = PROJECT_ROOT / "docker-compose.prod.yml"
COMPOSE_MONITORING = PROJECT_ROOT / "docker-compose-monitoring.yml"
COMPOSE_TRACING = PROJECT_ROOT / "docker-compose-tracing.yml"

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

def run_command(command, capture_output=False, shell=False):
    """Run a shell command with proper error handling"""
    try:
        if capture_output:
            result = subprocess.run(command, check=True, capture_output=True, text=True, shell=shell)
            return result.stdout
        else:
            subprocess.run(command, check=True, shell=shell)
            return True
    except subprocess.CalledProcessError as e:
        print_error(f"Error executing command: {command if isinstance(command, str) else ' '.join(command)}")
        print_error(f"{e}")
        return False

def build_services(env="dev", services=None):
    """Build Docker services"""
    compose_file = COMPOSE_DEV if env == "dev" else COMPOSE_PROD
    
    # Determine which env file to use
    env_file = ".env.prod" if env == "prod" else ".env.dev"
    
    print_info(f"Building services with {compose_file}...")
    
    if os.path.exists(env_file):
        # Safely build command as a list instead of using shell=True with string
        build_cmd = ["docker", "compose", "--env-file", env_file, "-f", str(compose_file), "build", "--no-cache"]
        if services:
            build_cmd.extend(services)
        
        if HAS_RICH:
            with Progress() as progress:
                task = progress.add_task("[green]Building...", total=1)
                success = run_command(build_cmd)
                progress.update(task, advance=1)
        else:
            success = run_command(build_cmd)
    else:
        if env == "prod":
            print_warning(f"No {env_file} found. Using default values (not secure for production).")
        
        build_cmd = ["docker", "compose", "-f", str(compose_file), "build", "--no-cache"]
        if services:
            build_cmd.extend(services)
        
        if HAS_RICH:
            with Progress() as progress:
                task = progress.add_task("[green]Building...", total=1)
                success = run_command(build_cmd)
                progress.update(task, advance=1)
        else:
            success = run_command(build_cmd)
    
    if success:
        print_success("Build completed successfully!")
    else:
        print_error("Build failed!")
        sys.exit(1)

def start_services(env, services=None):
    """Start Docker services with proper env file"""
    # Normalize and validate environment
    env = str(env).strip().lower()
    if env not in ["dev", "prod"]:
        print_error(f"Invalid environment: {env}. Must be 'dev' or 'prod'")
        sys.exit(1)
    
    # Set file paths based on environment
    compose_file = COMPOSE_PROD if env == "prod" else COMPOSE_DEV
    env_file = ".env.prod" if env == "prod" else ".env.dev"
    
    # Check for required files
    if not os.path.exists(compose_file):
        print_error(f"Missing compose file: {compose_file}")
        sys.exit(1)
    
    if not os.path.exists(env_file):
        print_error(f"Missing environment file: {env_file}")
        sys.exit(1)
    
    print_info(f"Using {env} environment with compose file: {compose_file}")
    print_info(f"Starting services with {compose_file}...")
    
    # Build and run command
    start_cmd = ["docker", "compose", "--env-file", env_file, "-f", str(compose_file), "up", "-d"]
    if services:
        start_cmd.extend(services)
    
    success = run_command(start_cmd)
    if not success:
        print_error("Failed to start services")
        sys.exit(1)
    
    return success
    """Stop Docker services"""
    compose_file = COMPOSE_DEV if env == "dev" else COMPOSE_PROD
    
    # Determine which env file to use for consistency
    env_file = ".env.prod" if env == "prod" else ".env.dev"
    
    print_info(f"Stopping services with {compose_file}...")
    
    if os.path.exists(env_file) and env == "prod":
        # Safely build command as a list instead of using shell=True with string
        stop_cmd = ["docker", "compose", "--env-file", env_file, "-f", str(compose_file), "down"]
        success = run_command(stop_cmd)
    else:
        stop_cmd = ["docker", "compose", "-f", str(compose_file), "down"]
        success = run_command(stop_cmd)
    
    if success:
        print_success("Services stopped successfully!")
    else:
        print_error("Failed to stop services!")
        sys.exit(1)

def check_services_health(env="dev"):
    """Check the health status of all services"""
    compose_file = COMPOSE_DEV if env == "dev" else COMPOSE_PROD
    env_file = ".env.prod" if env == "prod" else ".env.dev"
    
    print_info("Checking service health...")
    
    # Build command based on whether env file exists
    if os.path.exists(env_file) and env == "prod":
        ps_cmd = ["docker", "compose", "--env-file", env_file, "-f", str(compose_file), "ps", "--format", "json"]
    else:
        ps_cmd = ["docker", "compose", "-f", str(compose_file), "ps", "--format", "json"]
    
    # Get running containers
    containers = run_command(ps_cmd, capture_output=True)
    
    if not containers:
        print_warning("No running containers found.")
        return
    
    # Parse container information
    try:
        container_list = []
        for line in containers.strip().split('\n'):
            if line:
                container_list.append(json.loads(line))
    except json.JSONDecodeError:
        # Fallback to older format if json format is not available
        if os.path.exists(env_file) and env == "prod":
            ps_cmd = ["docker", "compose", "--env-file", env_file, "-f", str(compose_file), "ps"]
        else:
            ps_cmd = ["docker", "compose", "-f", str(compose_file), "ps"]
            
        containers = run_command(ps_cmd, capture_output=True)
        if not containers:
            print_warning("No running containers found.")
            return
        print_info(containers)
        return
    
    if HAS_RICH:
        table = Table(title="Service Health Status")
        table.add_column("Service", style="cyan")
        table.add_column("Status", style="magenta")
        table.add_column("Health", style="green")
        
        for container in container_list:
            name = container.get('Name', 'Unknown')
            status = container.get('State', 'Unknown')
            health = container.get('Health', 'No health check')
            
            # Determine health status display
            health_display = "❓ Unknown"
            if health == "healthy":
                health_display = "✅ Healthy"
            elif health == "unhealthy":
                health_display = "❌ Unhealthy"
            elif health == "starting":
                health_display = "🔄 Starting"
            elif status == "running":
                health_display = "⚠️ No health check"
            
            table.add_row(name, status, health_display)
        
        console.print(table)
    else:
        for container in container_list:
            name = container.get('Name', 'Unknown')
            status = container.get('State', 'Unknown')
            health = container.get('Health', 'No health check')
            print(f"Service: {name}, Status: {status}, Health: {health}")
    
    # Also try to check API health endpoint if available
    try:
        result = subprocess.run(
            ["curl", "-s", "http://localhost:8000/health"], 
            capture_output=True, 
            text=True, 
            check=False
        )
        if result.returncode == 0:
            print_info("API Health Check:")
            try:
                api_health = json.loads(result.stdout)
                for key, value in api_health.items():
                    print(f"  {key}: {value}")
            except json.JSONDecodeError:
                print_info(result.stdout)
    except Exception as e:
        print_warning(f"API health endpoint not reachable yet: {e}")

def scan_images(services=None):
    """Scan Docker images for vulnerabilities"""
    print_info("Scanning Docker images for vulnerabilities...")
    
    # Check if Docker Scout is available - use a more reliable check
    try:
        subprocess.run(
            ["docker", "scout", "version"], 
            capture_output=True, 
            text=True, 
            check=False
        )
        # Docker Scout exists if we get here (even if it returned an error code because we didn't provide a subcommand)
        scout_available = True
    except FileNotFoundError:
        scout_available = False
    
    if not scout_available:
        print_error("Docker Scout not available. Make sure Docker Desktop is updated.")
        return
    
    # Get list of images
    images_cmd = ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}"]
    images_output = run_command(images_cmd, capture_output=True)
    
    if not images_output:
        print_warning("No images found to scan.")
        return
    
    images = images_output.strip().split('\n')
    project_images = [img for img in images if not img.startswith('prom/') 
                     and not img.startswith('grafana/') 
                     and not img.startswith('redis:') 
                     and not img.startswith('postgres:')
                     and not img.endswith('<none>')]
    
    if services:
        # Filter images by service name
        project_images = [img for img in project_images if any(service in img for service in services)]
    
    for image in project_images:
        print_info(f"Scanning image: {image}")
        
        # Run Docker Scout scan
        scan_cmd = ["docker", "scout", "quickview", image]
        run_command(scan_cmd)
        
        # Ask if detailed scan is wanted
        answer = input("\nRun detailed scan? [y/N]: ")
        if answer.lower() == 'y':
            cves_cmd = ["docker", "scout", "cves", image]
            run_command(cves_cmd)
            
            # Ask if recommendations are wanted
            answer = input("\nShow recommendations? [y/N]: ")
            if answer.lower() == 'y':
                recommendations_cmd = ["docker", "scout", "recommendations", image]
                run_command(recommendations_cmd)

def run_tests(env="dev", test_path=None):
    """Run automated tests"""
    compose_file = COMPOSE_DEV if env == "dev" else COMPOSE_PROD
    
    # Determine which env file to use for consistency
    env_file = ".env.prod" if env == "prod" else ".env.dev"
    
    print_info("Running automated tests...")
    
    if not test_path:
        # Find all tests by gathering test directories
        test_dirs = []
        if (PROJECT_ROOT / "services/api/tests").exists():
            test_dirs.append("services/api/tests")
        if (PROJECT_ROOT / "services/frontend/tests").exists():
            test_dirs.append("services/frontend/tests")
        
        if not test_dirs:
            print_warning("No test directories found.")
            return
    else:
        test_dirs = [test_path]
    
    for test_dir in test_dirs:
        service_name = test_dir.split('/')[1]  # Extract service name
        print_info(f"Running tests for {service_name}...")
        
        if service_name == "api":
            # Run Python tests
            if os.path.exists(env_file) and env == "prod":
                test_cmd = ["docker", "compose", "--env-file", env_file, "-f", str(compose_file), "exec", "api", "pytest", "-xvs", test_dir]
            else:
                test_cmd = ["docker", "compose", "-f", str(compose_file), "exec", "api", "pytest", "-xvs", test_dir]
            
            run_command(test_cmd)
        elif service_name == "frontend":
            # Run JavaScript tests
            if os.path.exists(env_file) and env == "prod":
                test_cmd = ["docker", "compose", "--env-file", env_file, "-f", str(compose_file), "exec", "frontend", "npm", "test", "--", "--watchAll=false"]
            else:
                test_cmd = ["docker", "compose", "-f", str(compose_file), "exec", "frontend", "npm", "test", "--", "--watchAll=false"]
            
            run_command(test_cmd)

def show_logs(env="dev", service=None, tail=100):
    """Show logs for services"""
    compose_file = COMPOSE_DEV if env == "dev" else COMPOSE_PROD
    
    # Determine which env file to use for consistency
    env_file = ".env.prod" if env == "prod" else ".env.dev"
    
    if service:
        print_info(f"Showing logs for {service}...")
        if os.path.exists(env_file) and env == "prod":
            log_cmd = ["docker", "compose", "--env-file", env_file, "-f", str(compose_file), "logs", "--tail", str(tail), "-f", service]
        else:
            log_cmd = ["docker", "compose", "-f", str(compose_file), "logs", "--tail", str(tail), "-f", service]
        
        run_command(log_cmd)
    else:
        print_info("Showing logs for all services...")
        if os.path.exists(env_file) and env == "prod":
            log_cmd = ["docker", "compose", "--env-file", env_file, "-f", str(compose_file), "logs", "--tail", str(tail), "-f"]
        else:
            log_cmd = ["docker", "compose", "-f", str(compose_file), "logs", "--tail", str(tail), "-f"]
        
        run_command(log_cmd)

def start_monitoring():
    """Start the monitoring stack"""
    if not COMPOSE_MONITORING.exists():
        print_error(f"Monitoring compose file not found at {COMPOSE_MONITORING}")
        print_info("Run the setup-monitoring script first.")
        return
    
    print_info("Starting monitoring stack...")
    run_command(["docker", "compose", "-f", str(COMPOSE_MONITORING), "up", "-d"])
    print_success("Monitoring stack started!")
    print_info("Access Grafana at: http://localhost:3001 (admin/admin)")
    print_info("Access Prometheus at: http://localhost:9090")
    print_info("Access cAdvisor at: http://localhost:8080")
    print_info("Access Node Exporter metrics at: http://localhost:9100/metrics")

def stop_monitoring():
    """Stop the monitoring stack"""
    if not COMPOSE_MONITORING.exists():
        print_error(f"Monitoring compose file not found at {COMPOSE_MONITORING}")
        return
    
    print_info("Stopping monitoring stack...")
    run_command(["docker", "compose", "-f", str(COMPOSE_MONITORING), "down"])
    print_success("Monitoring stack stopped!")

def show_container_stats():
    """Show real-time stats of running containers"""
    print_info("Displaying container resource statistics...")
    
    # Check if any containers are running
    containers = run_command(['docker', 'ps', '--format', '{{.Names}}'], capture_output=True)
    if not containers:
        print_warning("No running containers found.")
        return
    
    # Use docker stats command to show real-time stats
    print_info("Press Ctrl+C to exit the stats view")
    time.sleep(1)
    
    try:
        # Run docker stats without truncating output and with human-readable format
        stats_cmd = ['docker', 'stats', '--no-trunc', '--format', 
                    'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}']
        # This is a blocking call that will show real-time stats
        subprocess.run(stats_cmd)
    except KeyboardInterrupt:
        print_info("\nExited stats view")
    except Exception as e:
        print_error(f"Error displaying stats: {e}")

def generate_dependency_graph():
    """Generate a dependency graph of the Docker services"""
    print_info("Generating service dependency graph...")
    
    # Check if graphviz is installed
    try:
        import graphviz
    except ImportError:
        print_error("Graphviz Python package not found. Install with: pip install graphviz")
        print_warning("Also ensure the Graphviz binary is installed on your system.")
        return
    
    # Read the compose files to extract dependencies
    try:
        import yaml
        
        # Try to read compose files
        dev_services = {}
        prod_services = {}
        
        if COMPOSE_DEV.exists():
            with open(COMPOSE_DEV, 'r') as f:
                dev_compose = yaml.safe_load(f)
                if dev_compose and 'services' in dev_compose:
                    dev_services = dev_compose['services']
        
        if COMPOSE_PROD.exists():
            with open(COMPOSE_PROD, 'r') as f:
                prod_compose = yaml.safe_load(f)
                if prod_compose and 'services' in prod_compose:
                    prod_services = prod_compose['services']
        
        if not dev_services and not prod_services:
            print_error("No services found in compose files.")
            return
        
        # Create a digraph for the dependencies
        dot = graphviz.Digraph(comment='Service Dependencies')
        
        # Add services as nodes
        all_services = set(list(dev_services.keys()) + list(prod_services.keys()))
        for service in all_services:
            dot.node(service, service)
        
        # Add dependencies as edges
        for service, config in {**dev_services, **prod_services}.items():
            if 'depends_on' in config:
                dependencies = config['depends_on']
                if isinstance(dependencies, list):
                    # Simple dependency list
                    for dependency in dependencies:
                        dot.edge(service, dependency)
                elif isinstance(dependencies, dict):
                    # Extended dependency syntax with conditions
                    for dependency in dependencies.keys():
                        dot.edge(service, dependency)
        
        # Render the graph
        try:
            dot.render('service_dependencies', format='png', cleanup=True)
            print_success("Dependency graph generated as 'service_dependencies.png'")
            # Try to open the image
            if sys.platform == 'darwin':  # macOS
                run_command(['open', 'service_dependencies.png'], shell=False)
            elif sys.platform.startswith('linux'):
                run_command(['xdg-open', 'service_dependencies.png'], shell=False)
            elif sys.platform == 'win32':  # Windows
                run_command(['start', 'service_dependencies.png'], shell=True)
        except Exception as e:
            print_error(f"Error rendering graph: {e}")
            print_info("Raw graph data is available in 'service_dependencies' file.")
        
    except ImportError:
        print_error("PyYAML package not found. Install with: pip install pyyaml")
    except Exception as e:
        print_error(f"Error generating dependency graph: {e}")

def network_check():
    """Test connectivity between services"""
    print_info("Checking network connectivity between services...")
    
    # Check if any containers are running
    containers = run_command(['docker', 'ps', '--format', '{{.Names}}'], capture_output=True)
    if not containers:
        print_warning("No running containers found.")
        return
    
    # Filter out buildx containers and other non-service containers
    container_list = containers.strip().split('\n')
    filtered_containers = [
        container for container in container_list 
        if "buildx_buildkit" not in container 
        and container.startswith("docker-microservices-project-")
    ]
    
    if not filtered_containers:
        print_warning("No relevant service containers found.")
        return
        
    if HAS_RICH:
        table = Table(title="Network Connectivity Test")
        table.add_column("Source", style="cyan")
        table.add_column("Target", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Latency", style="magenta")
    
    # Test connectivity between each pair of service containers
    for source in filtered_containers:
        # Extract service name for cleaner display
        source_name = source.replace("docker-microservices-project-", "").replace("-1", "")
        
        for target in filtered_containers:
            if source != target:
                # Extract service name for cleaner display
                target_name = target.replace("docker-microservices-project-", "").replace("-1", "")
                
                # Use ping to test connectivity
                ping_cmd = ["docker", "exec", source, "ping", "-c", "1", "-W", "1", target_name]
                result = subprocess.run(ping_cmd, capture_output=True, text=True, check=False)
                
                status = "✅ Connected" if result.returncode == 0 else "❌ Failed"
                
                # Extract latency if connected
                latency = "N/A"
                if result.returncode == 0:
                    import re
                    match = re.search(r"time=(\d+\.\d+) ms", result.stdout)
                    if match:
                        latency = f"{match.group(1)} ms"
                
                if HAS_RICH:
                    table.add_row(source_name, target_name, status, latency)
                else:
                    print(f"Source: {source_name}, Target: {target_name}, Status: {status}, Latency: {latency}")
    
    if HAS_RICH:
        console.print(table)
        
def restart_service(env="dev", service=None):
    """Restart a specific service"""
    if not service:
        print_error("Please specify a service to restart with --service")
        return
        
    compose_file = COMPOSE_DEV if env == "dev" else COMPOSE_PROD
    env_file = ".env.prod" if env == "prod" else ".env.dev"
    
    print_info(f"Restarting service: {service}...")
    
    # Build restart command
    if os.path.exists(env_file) and env == "prod":
        restart_cmd = ["docker", "compose", "--env-file", env_file, "-f", str(compose_file), "restart", service]
    else:
        restart_cmd = ["docker", "compose", "-f", str(compose_file), "restart", service]
    
    if run_command(restart_cmd):
        print_success(f"Service {service} restarted successfully!")
        time.sleep(3)  # Wait a bit for the service to be ready
        check_services_health(env)
    else:
        print_error(f"Failed to restart service {service}")

def scale_service(env="dev", service=None, replicas=1):
    """Scale a service to a specific number of replicas"""
    if not service:
        print_error("Please specify a service to scale with --service")
        return
    
    compose_file = COMPOSE_DEV if env == "dev" else COMPOSE_PROD
    env_file = ".env.prod" if env == "prod" else ".env.dev"
    
    # Check if the service is scalable
    non_scalable = ['db', 'redis', 'postgres', 'mysql', 'mongodb']
    if any(name in service.lower() for name in non_scalable):
        print_warning(f"Service {service} appears to be a database or stateful service.")
        confirm = input("Scaling stateful services can cause data inconsistency. Continue anyway? [y/N]: ")
        if confirm.lower() != 'y':
            print_info("Operation canceled.")
            return
    
    print_info(f"Scaling service {service} to {replicas} replicas...")
    
    # Build scale command
    if os.path.exists(env_file) and env == "prod":
        scale_cmd = ["docker", "compose", "--env-file", env_file, "-f", str(compose_file), "up", "-d", "--scale", f"{service}={replicas}"]
    else:
        scale_cmd = ["docker", "compose", "-f", str(compose_file), "up", "-d", "--scale", f"{service}={replicas}"]
    
    if run_command(scale_cmd):
        print_success(f"Service {service} scaled to {replicas} replicas!")
        time.sleep(3)  # Wait a bit for the services to be ready
        check_services_health(env)
    else:
        print_error(f"Failed to scale service {service}")

def security_check():
    """Check for security issues in the Docker environment"""
    print_info("Performing security check on Docker environment...")
    
    # List of checks to perform
    security_issues = []
    
    # 1. Check for containers running as root
    print_info("Checking for containers running as root...")
    containers = run_command(["docker", "ps", "--format", "{{.Names}}"], capture_output=True)
    
    if containers:
        for container in containers.strip().split('\n'):
            user_cmd = ["docker", "exec", container, "whoami"]
            result = subprocess.run(user_cmd, capture_output=True, text=True, check=False)
            if result.returncode == 0 and result.stdout.strip() == "root":
                security_issues.append(f"Container {container} is running as root user")
    
    # 2. Check for exposed ports that should be internal
    print_info("Checking for unnecessarily exposed ports...")
    port_cmd = ["docker", "ps", "--format", "{{.Names}}: {{.Ports}}"]
    ports = run_command(port_cmd, capture_output=True)
    
    sensitive_ports = ['5432', '6379', '27017', '3306']  # Database ports
    if ports:
        for line in ports.strip().split('\n'):
            for port in sensitive_ports:
                if f":{port}->" in line:
                    security_issues.append(f"Sensitive port {port} is publicly exposed in {line.split(':')[0]}")
    
    # 3. Check Docker version for known vulnerabilities
    print_info("Checking Docker version...")
    version_cmd = ["docker", "version", "--format", "{{.Server.Version}}"]
    version = run_command(version_cmd, capture_output=True)
    if version and version.strip() < "20.10":
        security_issues.append(f"Docker version {version.strip()} might have known vulnerabilities. Consider upgrading.")
    
    # 4. Check for containers with privileged mode
    print_info("Checking for privileged containers...")
    inspect_cmd = ["docker", "ps", "-q"]
    container_ids = run_command(inspect_cmd, capture_output=True)
    
    if container_ids:
        for cid in container_ids.strip().split('\n'):
            if cid:
                priv_cmd = ["docker", "inspect", "--format", "{{.Name}}: {{.HostConfig.Privileged}}", cid]
                priv_status = run_command(priv_cmd, capture_output=True)
                if priv_status and "true" in priv_status.lower():
                    security_issues.append(f"Container {priv_status.split(':')[0]} is running in privileged mode")
    
    # Display security issues in a table if Rich is available
    if HAS_RICH:
        if security_issues:
            table = Table(title="Security Issues Found")
            table.add_column("Issue", style="red")
            table.add_column("Recommendation", style="green")
            
            for issue in security_issues:
                recommendation = ""
                if "root user" in issue:
                    recommendation = "Use a non-root user in the Dockerfile with USER directive"
                elif "port" in issue:
                    recommendation = "Restrict this port to internal network only"
                elif "Docker version" in issue:
                    recommendation = "Update Docker to the latest stable release"
                elif "privileged mode" in issue:
                    recommendation = "Avoid privileged mode unless absolutely necessary"
                
                table.add_row(issue, recommendation)
            
            console.print(table)
        else:
            console.print("[green]✅ No security issues found![/green]")
    else:
        if security_issues:
            print("Security issues found:")
            for issue in security_issues:
                print(f"- {issue}")
        else:
            print("✅ No security issues found!")

def start_tracing():
    """Start the distributed tracing system"""
    print_info("Starting Jaeger tracing system...")
    
    # Check if compose file exists
    if not COMPOSE_TRACING.exists():
        print_error("Tracing compose file not found.")
        return
    
    run_command(["docker", "compose", "-f", str(COMPOSE_TRACING), "up", "-d"])
    print_success("Jaeger UI available at: http://localhost:16686")
    print_info("Note: You won't see any traces until services are instrumented.")

def stop_tracing():
    """Stop the distributed tracing system"""
    print_info("Stopping Jaeger tracing system...")
    
    # Check if compose file exists
    if not COMPOSE_TRACING.exists():
        print_error("Tracing compose file not found.")
        return
    
    run_command(["docker", "compose", "-f", str(COMPOSE_TRACING), "down"])
    print_success("Tracing system stopped!")

def check_tracing_status():
    """Check the status of the tracing system"""
    print_info("Checking Jaeger tracing system status...")
    
    # Check if Jaeger container is running
    result = run_command(["docker", "ps", "-q", "-f", "name=jaeger"], capture_output=True)
    
    if result and result.strip():
        print_success("✅ Jaeger is running")
        
        # Try to connect to Jaeger UI
        try:
            import urllib.request
            code = urllib.request.urlopen("http://localhost:16686").getcode()
            if code == 200:
                print_success("✅ Jaeger UI is accessible at: http://localhost:16686")
            else:
                print_warning(f"⚠️  Jaeger UI returned status code: {code}")
        except Exception as e:
            print_warning(f"⚠️  Couldn't connect to Jaeger UI: {e}")
    else:
        print_error("❌ Jaeger is not running")

def query_traces(service=None, operation=None, tags=None, limit=20):
    """Query traces from Jaeger and display results"""
    print_info("Querying traces from Jaeger...")
    
    # First check if Jaeger is running
    jaeger_check = run_command(
        ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "http://localhost:16686/api/services"],
        capture_output=True
    )
    if not jaeger_check or jaeger_check.strip() != "200":
        print_error("Jaeger is not running. Start it with: ./microservices start-tracing")
        return
    
    # Build query URL
    query_params = []
    if service:
        query_params.append(f"service={service}")
    if operation:
        query_params.append(f"operation={operation}")
    if tags:
        # Format tags as JSON: {"key":"value"}
        for key, value in tags.items():
            query_params.append(f'tags=%7B%22{key}%22%3A%22{value}%22%7D')
    
    query_params.append(f"limit={limit}")
    
    # If no parameters were provided, try to get all traces
    if not service and not operation and not tags:
        # Add a generous lookback period and limit
        lookback = int(time.time() * 1000000) - (24 * 3600 * 1000000)  # 24 hours in microseconds
        query_params.append(f"start={lookback}")
        query_params.append("limit=1000")  # Get more traces
    
    query_url = f"http://localhost:16686/api/traces?{'&'.join(query_params)}"
    print_info(f"Querying Jaeger: {query_url}")
    
    # Fetch traces
    try:
        result = subprocess.run(["curl", "-s", query_url], capture_output=True, text=True)
        if result.returncode != 0:
            print_error(f"Failed to query traces: {result.stderr}")
            return
        
        # Parse JSON response
        try:
            traces = json.loads(result.stdout)
            
            if not traces.get("data") or len(traces["data"]) == 0:
                print_warning("No traces found matching the criteria.")
                
                # If no traces were found but Jaeger is running, try to diagnose
                services_resp = subprocess.run(
                    ["curl", "-s", "http://localhost:16686/api/services"],
                    capture_output=True, text=True
                )
                try:
                    services_data = json.loads(services_resp.stdout)
                    if len(services_data) <= 1 and "jaeger-query" in services_data:
                        print_info("No services are reporting traces to Jaeger.")
                        print_info("Check that your applications are properly instrumented and running.")
                        print_info("Remember to generate some traffic to create traces.")
                    else:
                        print_info(f"Available services: {', '.join(services_data)}")
                        print_info("Try querying traces for a specific service.")
                except:
                    pass
                return
            
            # Display results in a table
            if HAS_RICH:
                table = Table(title=f"Traces ({len(traces['data'])} results)")
                table.add_column("Trace ID", style="cyan")
                table.add_column("Duration (ms)", style="magenta")
                table.add_column("Services", style="green")
                table.add_column("Operations", style="yellow")
                table.add_column("Start Time", style="blue")
                
                for trace in traces["data"]:
                    trace_id = trace.get("traceID", "Unknown")
                    
                    # Calculate duration in ms
                    duration_ms = 0
                    start_time = None
                    services = set()
                    operations = set()
                    
                    for span in trace.get("spans", []):
                        duration_ms = max(duration_ms, span.get("duration", 0) / 1000)  # Convert μs to ms
                        
                        # Track start time (lowest timestamp)
                        span_start = span.get("startTime", 0)
                        if start_time is None or span_start < start_time:
                            start_time = span_start
                        
                        # Track services and operations
                        process_id = span.get("processID")
                        if process_id and process_id in trace.get("processes", {}):
                            service_name = trace.get("processes", {}).get(process_id, {}).get("serviceName", "unknown")
                            services.add(service_name)
                        
                        operations.add(span.get("operationName", "unknown"))
                    
                    # Format start time
                    start_time_str = "Unknown"
                    if start_time:
                        start_time_date = datetime.datetime.fromtimestamp(start_time / 1000000)  # Convert μs to seconds
                        start_time_str = start_time_date.strftime("%Y-%m-%d %H:%M:%S")
                    
                    table.add_row(
                        trace_id,
                        f"{duration_ms:.2f}",
                        ", ".join(services),
                        ", ".join(list(operations)[:3]) + ("..." if len(operations) > 3 else ""),
                        start_time_str
                    )
                
                console.print(table)
                
                # Ask user if they want to open any trace in the browser
                trace_to_open = console.input("Enter trace ID to open in browser (or press Enter to skip): ")
                if trace_to_open:
                    trace_url = f"http://localhost:16686/trace/{trace_to_open}"
                    
                    if sys.platform == 'darwin':  # macOS
                        run_command(['open', trace_url], shell=False)
                    elif sys.platform.startswith('linux'):
                        run_command(['xdg-open', trace_url], shell=False)
                    elif sys.platform == 'win32':  # Windows
                        run_command(['start', trace_url], shell=True)
                    
                    print_info(f"Opening trace: {trace_url}")
            else:
                # Simple output for non-rich environments
                print("Traces found:")
                for i, trace in enumerate(traces["data"], 1):
                    trace_id = trace.get("traceID", "Unknown")
                    spans = len(trace.get("spans", []))
                    services = set()
                    
                    for span in trace.get("spans", []):
                        process_id = span.get("processID")
                        if process_id and process_id in trace.get("processes", {}):
                            service_name = trace.get("processes", {}).get(process_id, {}).get("serviceName", "unknown")
                            services.add(service_name)
                    
                    print(f"{i}. Trace ID: {trace_id}, Spans: {spans}, Services: {', '.join(services)}")
        except json.JSONDecodeError:
            print_error("Failed to parse Jaeger response. Is Jaeger running?")
            print_info("Response: " + result.stdout[:100] + "..." if len(result.stdout) > 100 else result.stdout)
    except Exception as e:
        print_error(f"Error querying traces: {e}")
        
def set_sampling_rate(service, rate):
    """Set the sampling rate for a service"""
    if service not in ["api", "frontend"]:
        print_error(f"Unsupported service: {service}. Use 'api' or 'frontend'.")
        return
    
    compose_file = COMPOSE_DEV  # Use dev compose file by default
    
    rate_float = float(rate)
    if rate_float < 0 or rate_float > 1:
        print_error("Sampling rate must be between 0 and 1 (e.g., 0.1 for 10% sampling)")
        return
    
    if service == "api":
        # Update environment variable in API service
        print_info(f"Setting API sampling rate to {rate_float}...")
        
        # First, check current rate
        current_config = run_command(
            ["docker", "compose", "-f", str(compose_file), "exec", "api", "printenv", "OTEL_TRACES_SAMPLER_ARG"],
            capture_output=True
        )
        
        print_info(f"Current sampling rate: {current_config or 'not set'}")
        
        # Apply new configuration
        env_vars = {
            "OTEL_TRACES_SAMPLER": "parentbased_traceidratio",
            "OTEL_TRACES_SAMPLER_ARG": str(rate_float)
        }
        
        for var_name, var_value in env_vars.items():
            run_command(["docker", "compose", "-f", str(compose_file), "exec", "api", "sh", "-c", f"export {var_name}={var_value}"])
        
        print_warning("Note: Changes require service restart to take full effect.")
        restart = input("Restart API service now? [y/N]: ")
        if restart.lower() == 'y':
            run_command(["docker", "compose", "-f", str(compose_file), "restart", "api"])
            print_success("API service restarted with new sampling rate.")
        else:
            print_info("Changes will take effect on next service restart.")
    
    elif service == "frontend":
        # For frontend, we need to modify the environment variables in the container
        print_info(f"Setting frontend sampling rate to {rate_float}...")
        
        # This is more complex for frontend since it's built into the app
        print_warning("For frontend, sampling rate changes require rebuilding the service.")
        rebuild = input("Rebuild frontend with new sampling rate? [y/N]: ")
        if rebuild.lower() == 'y':
            # Create a temporary Dockerfile with the new sampling rate
            with open("services/frontend/Dockerfile.temp", "w") as f:
                f.write(f"""# Temporary Dockerfile with custom sampling rate
FROM docker-microservices-project-frontend
ENV REACT_APP_OTEL_SAMPLING_RATIO={rate_float}
""")
            
            run_command(["docker", "build", "-t", "frontend-custom-sampling", "-f", "services/frontend/Dockerfile.temp", "services/frontend"])
            run_command(["docker", "compose", "-f", str(compose_file), "stop", "frontend"])
            run_command(["docker", "compose", "-f", str(compose_file), "rm", "-f", "frontend"])
            
            # Update the compose file to use the custom image
            # This is a simplified approach - in practice you'd want to update the compose file properly
            run_command(["docker", "run", "-d", "--name", "frontend", "--network", "microservices_app-network", "-p", "80:80", "frontend-custom-sampling"])
            
            print_success("Frontend rebuilt with new sampling rate.")
        else:
            print_info("No changes applied.")

def generate_trace_summary(days=1):
    """Generate a summary of traces over the specified number of days"""
    print_info(f"Generating trace summary for the past {days} days...")
    
    # Calculate timestamp for start of the period (in microseconds)
    start_time = int((datetime.datetime.now() - datetime.timedelta(days=days)).timestamp() * 1000000)
    
    # Query all traces since that time
    query_url = f"http://localhost:16686/api/traces?start={start_time}&limit=1000"
    
    try:
        result = subprocess.run(["curl", "-s", query_url], capture_output=True, text=True)
        if result.returncode != 0:
            print_error(f"Failed to query traces: {result.stderr}")
            return
        
        # Parse JSON response
        try:
            traces = json.loads(result.stdout)
            
            if not traces.get("data") or len(traces["data"]) == 0:
                print_warning("No traces found for the specified period.")
                return
            
            # Analyze trace data
            trace_count = len(traces["data"])
            
            # Count by service
            services_count = {}
            # Track durations
            durations = []
            # Track span counts
            span_counts = []
            # Track error counts
            error_count = 0
            
            for trace in traces["data"]:
                # Count spans
                spans = trace.get("spans", [])
                span_counts.append(len(spans))
                
                # Track max duration
                max_duration = 0
                
                for span in spans:
                    max_duration = max(max_duration, span.get("duration", 0))
                    
                    # Check for errors
                    for tag in span.get("tags", []):
                        if tag.get("key") == "error" and tag.get("value") == "true":
                            error_count += 1
                            break
                    
                    # Track services
                    process_id = span.get("processID")
                    if process_id and process_id in trace.get("processes", {}):
                        service_name = trace.get("processes", {}).get(process_id, {}).get("serviceName", "unknown")
                        services_count[service_name] = services_count.get(service_name, 0) + 1
                
                # Convert duration to milliseconds
                durations.append(max_duration / 1000)
            
            # Calculate statistics
            avg_duration = sum(durations) / len(durations) if durations else 0
            max_duration = max(durations) if durations else 0
            min_duration = min(durations) if durations else 0
            p95_duration = sorted(durations)[int(len(durations) * 0.95)] if durations else 0
            
            avg_spans = sum(span_counts) / len(span_counts) if span_counts else 0
            max_spans = max(span_counts) if span_counts else 0
            
            error_rate = (error_count / sum(span_counts)) * 100 if span_counts else 0
            
            # Print summary
            if HAS_RICH:
                console.print("[bold]Trace Summary[/bold]")
                console.print(f"Period: Past {days} days")
                console.print(f"Total Traces: {trace_count}")
                console.print(f"Total Spans: {sum(span_counts)}")
                console.print(f"Error Rate: {error_rate:.2f}%")
                
                console.print("\n[bold]Duration Statistics (ms)[/bold]")
                console.print(f"Average: {avg_duration:.2f}")
                console.print(f"Minimum: {min_duration:.2f}")
                console.print(f"Maximum: {max_duration:.2f}")
                console.print(f"95th Percentile: {p95_duration:.2f}")
                
                console.print("\n[bold]Span Statistics[/bold]")
                console.print(f"Average Spans per Trace: {avg_spans:.2f}")
                console.print(f"Maximum Spans in a Trace: {max_spans}")
                
                # Service distribution table
                table = Table(title="Service Distribution")
                table.add_column("Service", style="cyan")
                table.add_column("Span Count", style="magenta")
                table.add_column("Percentage", style="green")
                
                total_spans = sum(services_count.values())
                for service, count in sorted(services_count.items(), key=lambda x: x[1], reverse=True):
                    percentage = (count / total_spans) * 100 if total_spans else 0
                    table.add_row(service, str(count), f"{percentage:.2f}%")
                
                console.print(table)
            else:
                print("Trace Summary")
                print(f"Period: Past {days} days")
                print(f"Total Traces: {trace_count}")
                print(f"Total Spans: {sum(span_counts)}")
                print(f"Error Rate: {error_rate:.2f}%")
                
                print("\nDuration Statistics (ms)")
                print(f"Average: {avg_duration:.2f}")
                print(f"Minimum: {min_duration:.2f}")
                print(f"Maximum: {max_duration:.2f}")
                print(f"95th Percentile: {p95_duration:.2f}")
                
                print("\nSpan Statistics")
                print(f"Average Spans per Trace: {avg_spans:.2f}")
                print(f"Maximum Spans in a Trace: {max_spans}")
                
                print("\nService Distribution")
                total_spans = sum(services_count.values())
                for service, count in sorted(services_count.items(), key=lambda x: x[1], reverse=True):
                    percentage = (count / total_spans) * 100 if total_spans else 0
                    print(f"{service}: {count} spans ({percentage:.2f}%)")
        
        except json.JSONDecodeError:
            print_error("Failed to parse Jaeger response. Is Jaeger running?")
    
    except Exception as e:
        print_error(f"Error generating trace summary: {e}")

def benchmark_api(endpoint="/health", requests=100, concurrency=10):
    """
    Run a performance benchmark against the API with tracing enabled
    and compare with tracing disabled
    """
    compose_file = COMPOSE_DEV  # Use dev compose file by default
    
    print_info(f"Benchmarking API endpoint: {endpoint}")
    print_info(f"Requests: {requests}, Concurrency: {concurrency}")
    
    results = {}
    
    # Check if Apache Benchmark is installed
    ab_installed = run_command(["which", "ab"], capture_output=True)
    if not ab_installed:
        print_error("Apache Benchmark (ab) not found. Please install apache2-utils.")
        return
    
    for mode in ["tracing", "no-tracing"]:
        print_info(f"\nRunning benchmark with {mode}...")
        
        # Configure tracing based on mode
        if mode == "tracing":
            run_command(["docker", "compose", "-f", str(compose_file), "exec", "-e", "ENABLE_TRACING=true", "api", "sh", "-c", "echo 'Tracing enabled'"])
        else:
            run_command(["docker", "compose", "-f", str(compose_file), "exec", "-e", "ENABLE_TRACING=false", "api", "sh", "-c", "echo 'Tracing disabled'"])
        
        # Need to restart API to apply changes
        print_info("Restarting API to apply tracing changes...")
        run_command(["docker", "compose", "-f", str(compose_file), "restart", "api"])
        time.sleep(5)  # Wait for API to be ready
        
        # Check if the endpoint requires authentication
        requires_auth = endpoint not in ["/health", "/", "/metrics"]
        
        # Prepare command
        if requires_auth:
            print_warning(f"Endpoint {endpoint} may require authentication.")
            print_info("Skipping authentication for benchmark.")
        
        print_info(f"Running benchmark against http://localhost:8000{endpoint}...")
        benchmark_cmd = ["ab", "-n", str(requests), "-c", str(concurrency), f"http://localhost:8000{endpoint}"]
        
        # Run benchmark
        result = subprocess.run(benchmark_cmd, capture_output=True, text=True)
        
        # Parse results
        if result.returncode != 0:
            print_error(f"Benchmark failed: {result.stderr}")
            continue
        
        # Extract key metrics
        output = result.stdout
        
        # Parse the output for key metrics
        metrics = {}
        
        # Requests per second
        rps_match = re.search(r"Requests per second:\s+([\d.]+)", output)
        if rps_match:
            metrics["rps"] = float(rps_match.group(1))
        
        # Time per request
        tpr_match = re.search(r"Time per request:\s+([\d.]+)", output)
        if tpr_match:
            metrics["time_per_request"] = float(tpr_match.group(1))
        
        # 50th percentile
        p50_match = re.search(r"50%\s+([\d]+)", output)
        if p50_match:
            metrics["p50"] = int(p50_match.group(1))
        
        # 95th percentile
        p95_match = re.search(r"95%\s+([\d]+)", output)
        if p95_match:
            metrics["p95"] = int(p95_match.group(1))
        
        # 99th percentile
        p99_match = re.search(r"99%\s+([\d]+)", output)
        if p99_match:
            metrics["p99"] = int(p99_match.group(1))
        
        # Store results
        results[mode] = metrics
    
    # Compare results
    if "tracing" in results and "no-tracing" in results:
        if HAS_RICH:
            table = Table(title="Benchmark Results Comparison")
            table.add_column("Metric", style="cyan")
            table.add_column("With Tracing", style="magenta")
            table.add_column("Without Tracing", style="green")
            table.add_column("Difference", style="yellow")
            
            # Add metrics rows
            for metric in ["rps", "time_per_request", "p50", "p95", "p99"]:
                if metric in results["tracing"] and metric in results["no-tracing"]:
                    with_tracing = results["tracing"][metric]
                    without_tracing = results["no-tracing"][metric]
                    diff = with_tracing - without_tracing
                    diff_percent = (diff / without_tracing) * 100
                    
                    # Format based on metric
                    if metric == "rps":
                        metric_name = "Requests per second"
                        with_tracing_str = f"{with_tracing:.2f}"
                        without_tracing_str = f"{without_tracing:.2f}"
                        diff_str = f"{diff:.2f} ({diff_percent:+.2f}%)"
                    elif metric == "time_per_request":
                        metric_name = "Time per request (ms)"
                        with_tracing_str = f"{with_tracing:.2f}"
                        without_tracing_str = f"{without_tracing:.2f}"
                        diff_str = f"{diff:.2f} ({diff_percent:+.2f}%)"
                    else:
                        metric_name = f"{metric} response time (ms)"
                        with_tracing_str = str(with_tracing)
                        without_tracing_str = str(without_tracing)
                        diff_str = f"{diff} ({diff_percent:+.2f}%)"
                    
                    table.add_row(metric_name, with_tracing_str, without_tracing_str, diff_str)
            
            console.print(table)
        else:
            print("\nBenchmark Results Comparison:")
            print(f"{'Metric':<25} {'With Tracing':<15} {'Without Tracing':<15} {'Difference':<15}")
            print("-" * 70)
            
            for metric in ["rps", "time_per_request", "p50", "p95", "p99"]:
                if metric in results["tracing"] and metric in results["no-tracing"]:
                    with_tracing = results["tracing"][metric]
                    without_tracing = results["no-tracing"][metric]
                    diff = with_tracing - without_tracing
                    diff_percent = (diff / without_tracing) * 100
                    
                    # Format based on metric
                    if metric == "rps":
                        metric_name = "Requests per second"
                        print(f"{metric_name:<25} {with_tracing:.2f:<15.2f} {without_tracing:.2f:<15.2f} {diff:.2f} ({diff_percent:+.2f}%)")
                    elif metric == "time_per_request":
                        metric_name = "Time per request (ms)"
                        print(f"{metric_name:<25} {with_tracing:.2f:<15.2f} {without_tracing:.2f:<15.2f} {diff:.2f} ({diff_percent:+.2f}%)")
                    else:
                        metric_name = f"{metric} response time (ms)"
                        print(f"{metric_name:<25} {with_tracing:<15} {without_tracing:<15} {diff} ({diff_percent:+.2f}%)")
    
    else:
        print_error("Could not compare results. Ensure both benchmarks completed successfully.")
    
    # Restore tracing to enabled state
    run_command(["docker", "compose", "-f", str(compose_file), "exec", "-e", "ENABLE_TRACING=true", "api", "sh", "-c", "echo 'Restoring tracing to enabled state'"])
    run_command(["docker", "compose", "-f", str(compose_file), "restart", "api"])
    print_info("API service restarted with tracing enabled.")

def integrate_slo_commands(args_list):
    """Integrate SLO management commands"""
    try:
        from scripts.slo_manager import slo_command_handler
        slo_command_handler(args_list)
    except ImportError:
        print_error("SLO management module not found.")
        print_info("Make sure scripts/slo_manager.py exists and is executable.")
    except Exception as e:
        print_error(f"Error executing SLO command: {e}")

def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(description="Docker Microservices Project CLI")
    
    # Original commands
    parser.add_argument("command", choices=[
        "build", "start", "stop", "status", "scan", "test", "logs",
        "start-monitoring", "stop-monitoring", "stats", "dependency-graph", 
        "network-check", "restart", "scale", "security-check", 
        "start-tracing", "stop-tracing", "check-tracing",
        # Tracing commands
        "query-traces", "sampling-rate", "trace-summary", "slo", "benchmark",
        "all"
    ], help="Command to execute")
    
    # Existing arguments
    parser.add_argument("--env", choices=["dev", "prod"], required=True, 
                        help="Environment (dev or prod)")
    parser.add_argument("--services", nargs="+", 
                        help="Specific services to target")
    parser.add_argument("--tail", type=int, default=100, 
                        help="Number of log lines to show")
    parser.add_argument("--test-path", type=str,
                        help="Specific test path to run")
    parser.add_argument("--service", type=str, 
                        help="Specific service to target for single-service operations")
    parser.add_argument("--replicas", type=int, 
                        help="Number of replicas for scaling")
    parser.add_argument("--subcommand", dest="subcommand", help="Subcommand for multi-level commands")
    parser.add_argument("subargs", nargs=argparse.REMAINDER, help=argparse.SUPPRESS)
    # New tracing-specific arguments
    parser.add_argument("--operation", type=str,
                       help="Filter traces by operation name")
    parser.add_argument("--tag", nargs="+",
                       help="Filter traces by tags (format: key=value)")
    parser.add_argument("--limit", type=int, default=20,
                       help="Limit number of traces to query")
    parser.add_argument("--rate", type=float,
                       help="Sampling rate (0.0-1.0) for tracing")
    parser.add_argument("--days", type=int, default=1,
                       help="Number of days to include in trace summary")
    parser.add_argument("--requests", type=int, default=100,
                       help="Number of requests for benchmarking")
    parser.add_argument("--concurrency", type=int, default=10,
                       help="Concurrency level for benchmarking")
    parser.add_argument("--endpoint", type=str, default="/health",
                       help="API endpoint for benchmarking")
    
    args = parser.parse_args()

    environment = args.env
    print_info(f"Using environment: {environment}")
    
    # Display startup banner
    if HAS_RICH:
        console.print("[bold magenta]=====================================[/bold magenta]")
        console.print("[bold magenta]Docker Microservices Project Manager[/bold magenta]")
        console.print("[bold magenta]=====================================[/bold magenta]")
    else:
        print("=====================================")
        print("Docker Microservices Project Manager")
        print("=====================================")
    
    # Handle original commands
    if args.command == "build":
        build_services(args.env, args.services)
    
    elif args.command == "start":
        print(f"Debug: Before calling start_services, env = {args.env}")
        print(f"Debug: Calling start_services with env = {args.env}")
        start_services(environment, args.services)
    
    elif args.command == "stop":
        stop_services(args.env)
    
    elif args.command == "status":
        check_services_health(args.env)
    
    elif args.command == "scan":
        scan_images(args.services)
    
    elif args.command == "test":
        run_tests(args.env, args.test_path)
    
    elif args.command == "logs":
        show_logs(args.env, args.services[0] if args.services else None, args.tail)
    
    elif args.command == "start-monitoring":
        start_monitoring()
    
    elif args.command == "stop-monitoring":
        stop_monitoring()

    elif args.command == "dependency-graph":
        generate_dependency_graph()

    elif args.command == "stats":
        show_container_stats()

    elif args.command == "network-check":
       network_check()

    elif args.command == "restart":
        if not args.service and args.services:
            restart_service(args.env, args.services[0])
        elif not args.service and not args.services:
            print_error("Please specify a service to restart with --service")
        else:
            restart_service(args.env, args.service)

    elif args.command == "scale":
        if not args.service:
            print_error("Please specify a service to scale with --service")
        else:
            replicas = args.replicas if args.replicas else 1
            scale_service(args.env, args.service, replicas)

    elif args.command == "security-check":
        security_check()

    elif args.command == "start-tracing":
         start_tracing()

    elif args.command == "stop-tracing":
         stop_tracing()

    elif args.command == "check-tracing":
          check_tracing_status()
    elif args.command == "slo":
       if not args.subcommand:
          print_error("SLO command requires a subcommand. Try 'slo status', 'slo alerts', or 'slo test'")
       else:
           slo_args = [args.subcommand] + (args.subargs if args.subargs else [])
           integrate_slo_commands(slo_args)
    # Handle tracing commands
    elif args.command == "query-traces":
        service = args.service
        operation = args.operation
        tags = {}
        if args.tag:
            for tag_pair in args.tag:
                if '=' in tag_pair:
                    key, value = tag_pair.split('=', 1)
                    tags[key] = value
        limit = args.limit
        query_traces(service, operation, tags, limit)
    
    elif args.command == "sampling-rate":
        if not args.service:
            print_error("Please specify a service with --service (api or frontend)")
            return
        if args.rate is None:
            print_error("Please specify a sampling rate with --rate (0.0-1.0)")
            return
        set_sampling_rate(args.service, args.rate)
    
    elif args.command == "trace-summary":
        days = args.days
        generate_trace_summary(days)
    
    elif args.command == "benchmark":
        endpoint = args.endpoint
        requests = args.requests
        concurrency = args.concurrency
        benchmark_api(endpoint, requests, concurrency)

    elif args.command == "all":
        build_services(args.env, args.services)
        start_services(args.env, args.services)
        time.sleep(10)  # Give services more time to fully initialize
        check_services_health(args.env)
        run_tests(args.env)
        scan_images(args.services)

if __name__ == "__main__":
    main()
