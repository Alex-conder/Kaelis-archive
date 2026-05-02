#!/usr/bin/env python3
"""
Kaelis Experience Engine - KECL 
: kaelis experience <journey_name>
     kaelis experience --list
"""

import yaml
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

class FailureAction(Enum):
    HALT = "halt"
    CONTINUE = "continue"
    SUGGEST_MANUAL = "suggest_manual"

@dataclass
class PhaseResult:
    name: str
    success: bool
    output: str
    error: Optional[str] = None

class ExperienceEngine:
    def __init__(self, contract_path: str = ".kaelis/experience.yaml"):
        self.contract_path = Path(contract_path)
        self.contract = self._load_contract()
        self.results: List[PhaseResult] = []
        self.background_processes = []
    
    def _load_contract(self) -> Dict:
        """"""
        if not self.contract_path.exists():
            print(f"[ERROR] : {self.contract_path}")
            print("[INFO]  .kaelis/experience.yaml")
            sys.exit(1)
        
        with open(self.contract_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def execute_phase(self, phase: Dict, journey_context: Dict) -> PhaseResult:
        """"""
        name = phase.get('name', 'unnamed')
        print(f"\n[{'='*50}")
        print(f"[PHASE] {name}")
        if 'description' in phase:
            print(f"[DESC]  {phase['description']}")
        print(f"[{'='*50}")
        
        # 
        depends_on = phase.get('depends_on', [])
        if isinstance(depends_on, str):
            depends_on = [depends_on]
        
        for dep in depends_on:
            dep_result = next((r for r in self.results if r.name == dep), None)
            if not dep_result or not dep_result.success:
                return PhaseResult(
                    name, 
                    False, 
                    "", 
                    f": {dep}"
                )
        
        # 
        if phase.get('manual'):
            print(f"\n[MANUAL] :")
            print(phase.get('instructions', ''))
            response = input("\n Enter  ( 'skip' ): ")
            if response.lower() == 'skip':
                return PhaseResult(name, False, "skipped", "")
            return PhaseResult(name, True, "completed manually")
        
        # 
        if 'command' in phase:
            return self._execute_command(phase)
        
        # 
        if 'contract' in phase:
            return self._handle_contract(phase)
        
        return PhaseResult(name, False, "", "")
    
    def _execute_command(self, phase: Dict) -> PhaseResult:
        """ shell """
        cmd = phase['command']
        name = phase.get('name', 'command')
        background = phase.get('background', False)
        
        print(f"[EXEC] {cmd}")
        
        if background:
            print(f"[INFO] : {name}")
            try:
                process = subprocess.Popen(
                    cmd,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                self.background_processes.append((name, process))
                
                # 
                if 'health_check' in phase:
                    health = phase['health_check']
                    endpoint = health.get('endpoint')
                    timeout = health.get('timeout', 30)
                    
                    print(f"[WAIT]  ({timeout}s)...")
                    start = time.time()
                    while time.time() - start < timeout:
                        try:
                            urllib.request.urlopen(endpoint, timeout=2)
                            print(f"[OK] : {endpoint}")
                            return PhaseResult(name, True, f"started on {endpoint}")
                        except Exception:
                            time.sleep(1)
                    
                    return PhaseResult(name, False, "", "")
                
                return PhaseResult(name, True, "started in background")
            except Exception as e:
                return PhaseResult(name, False, "", str(e))
        
        # 
        try:
            result = subprocess.run(
                cmd, 
                shell=True, 
                capture_output=True, 
                text=True, 
                timeout=300
            )
            
            success = result.returncode == 0
            output = result.stdout + result.stderr
            
            if success:
                print(f"[OK] ")
                if output:
                    print(output[-500:])  # 500
            else:
                print(f"[FAIL] ")
                print(output[-1000:])
            
            return PhaseResult(name, success, output)
        except subprocess.TimeoutExpired:
            return PhaseResult(name, False, "", " (300s)")
        except Exception as e:
            return PhaseResult(name, False, "", str(e))
    
    def _handle_contract(self, phase: Dict) -> PhaseResult:
        """"""
        contract_file = phase['contract']
        name = phase.get('name', 'contract')
        
        print(f"[CONTRACT] : {contract_file}")
        
        if 'frontend.yaml' in contract_file:
            return self._handle_frontend_contract()
        elif 'bootstrap.yaml' in contract_file:
            return self._handle_bootstrap_contract()
        elif 'electron.yaml' in contract_file:
            return self._handle_electron_contract()
        else:
            return PhaseResult(name, False, "", f": {contract_file}")
    
    def _handle_frontend_contract(self) -> PhaseResult:
        """ -  React """
        frontend_dir = Path("web/frontend")
        
        # 
        if (frontend_dir / "package.json").exists():
            print("[INFO] ")
            return PhaseResult("frontend_init", True, "already exists")
        
        print("[GEN] ...")
        
        try:
            # 
            frontend_dir.mkdir(parents=True, exist_ok=True)
            
            #  Vite 
            result = subprocess.run(
                ["npm", "create", "vite@latest", ".", "--", "--template", "react-ts"],
                cwd=str(frontend_dir),
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode != 0:
                return PhaseResult("frontend_init", False, result.stderr, "Vite ")
            
            print("[INFO] ...")
            result = subprocess.run(
                ["npm", "install"],
                cwd=str(frontend_dir),
                capture_output=True,
                text=True,
                timeout=180
            )
            
            if result.returncode != 0:
                return PhaseResult("frontend_init", False, result.stderr, "npm install ")
            
            print("[OK] ")
            return PhaseResult("frontend_init", True, "generated successfully")
            
        except Exception as e:
            return PhaseResult("frontend_init", False, "", str(e))
    
    def _handle_bootstrap_contract(self) -> PhaseResult:
        """ - """
        print("[CHECK] ...")
        
        checks = [
            ("python --version", "Python 3.9+"),
            ("node --version", "Node.js 16+"),
            ("npm --version", "npm"),
        ]
        
        all_passed = True
        for cmd, name in checks:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                version = result.stdout.strip() or result.stderr.strip()
                print(f"  [OK] {name}: {version[:30]}")
            else:
                print(f"  [MISSING] {name}")
                all_passed = False
        
        return PhaseResult(
            "bootstrap", 
            all_passed, 
            "all checks passed" if all_passed else "some checks failed"
        )
    
    def _handle_electron_contract(self) -> PhaseResult:
        """ Electron """
        print("[INFO] Electron  (Phase 2)")
        return PhaseResult("electron_package", True, "not implemented yet")
    
    def run_journey(self, journey_name: str) -> bool:
        """"""
        journeys = self.contract.get('journeys', {})
        
        if journey_name not in journeys:
            print(f"[ERROR] : {journey_name}")
            print(f"[INFO] : {', '.join(journeys.keys())}")
            return False
        
        journey = journeys[journey_name]
        project_name = self.contract.get('project', {}).get('name', 'Kaelis')
        
        print(f"\n{'='*60}")
        print(f">>> {project_name} - {journey.get('description', journey_name)}")
        print(f"{'='*60}")
        
        for phase in journey.get('phases', []):
            result = self.execute_phase(phase, journey)
            self.results.append(result)
            
            if not result.success:
                on_failure = phase.get('on_failure', 'halt')
                
                if on_failure == 'halt':
                    print(f"\n[STOP] : {result.name}")
                    if result.error:
                        print(f"[ERROR] {result.error}")
                    self._print_summary()
                    return False
                
                elif on_failure == 'suggest_manual':
                    print(f"\n[WARN] : {result.name}")
                    if result.error:
                        print(f"[HINT] {result.error}")
                    response = input("? (y/n): ")
                    if response.lower() != 'y':
                        self._print_summary()
                        return False
        
        self._print_summary()
        return True
    
    def _print_summary(self):
        """"""
        print(f"\n{'='*60}")
        print(" ")
        print(f"{'='*60}")
        
        for r in self.results:
            status = "[OK]" if r.success else "[FAIL]"
            print(f"  {status} {r.name}")
        
        passed = sum(1 for r in self.results if r.success)
        total = len(self.results)
        print(f"\n: {passed}/{total} ")
        print(f"{'='*60}")
        
        # 
        for name, process in self.background_processes:
            print(f"[INFO] : {name} (PID: {process.pid})")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Kaelis Experience Engine - KECL ',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
:
  kaelis experience first_time_user    # 
  kaelis experience dev_quickstart     # 
  kaelis experience --list             # 
        """
    )
    
    parser.add_argument(
        'journey', 
        nargs='?',
        default='first_time_user',
        help=' (: first_time_user)'
    )
    parser.add_argument(
        '--list', 
        '-l',
        action='store_true', 
        help=''
    )
    
    args = parser.parse_args()
    
    engine = ExperienceEngine()
    
    if args.list:
        journeys = engine.contract.get('journeys', {})
        project = engine.contract.get('project', {}).get('name', 'Kaelis')
        print(f"\n {project} :")
        print("-" * 50)
        for name, journey in journeys.items():
            desc = journey.get('description', 'No description')
            phases = len(journey.get('phases', []))
            print(f"  {name:20} - {desc}")
            print(f"  {' '*20}   ({phases} )")
            print()
        return
    
    success = engine.run_journey(args.journey)
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()
