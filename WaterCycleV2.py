"""
## Acknowledgments & Inspirations

This WaterCycle game was inspired by patterns and techniques from several 
open-source Python/Tkinter projects:

### Game State Management
- **xyzen/xyGames** - Adapted the Game class state management pattern (NEW_GAME, 
  ACTIVE, PAUSED, GAME_OVER, GAME_WON) and score tracking system. Extended with 
  resource-specific state (water levels, event timers, win conditions).
  
- **akmalmzamri/python-knife-hit** - Studied the GameManager class architecture 
  with threading for delayed game triggers.

### UI & Visual Elements
- **tisnik/presentations** (Python_GUI/Tkinter/53_menu_images.py) - Referenced 
  PhotoImage loading patterns for icons in menus. Applied similar concepts using 
  emoji/unicode symbols throughout the interface.
  
- **pythonprogramming.altervista.org** - Studied toolbar button creation with 
  icons and compound layouts. Adapted for sector allocation buttons.

### Game Loop Architecture
- **Kent D. Lee's Game Development Tutorial** - Adapted the `root.after()` 
  recursive timer pattern and datetime-based elapsed time tracking for the 
  5-minute win condition.
  
- **Deformater/tkinter_doom** - Referenced dependency injection pattern (passing 
  UI components to game logic classes) and event binding structure.

All code was written from scratch implementing unique water resource management 
mechanics, multi-sector consumption systems, and urgent event-driven gameplay.
"""
import tkinter as tk
from tkinter import ttk
import random
import time
import json
import os
from datetime import datetime


# ========================================
# SECTOR CLASS
# ========================================
class Sector:
    def __init__(self, name, consumption_range, risk_threshold=20):
        self.name = name
        self.water_level = 100
        self.max_water = 100
        self.consumption_range = consumption_range
        self.risk_threshold = risk_threshold
        self.total_consumed = 0
        self.total_allocated = 0
        self.critical_warnings = 0
    
    def consume(self):
        """Consume random amount of water based on consumption range"""
        consumption = random.randint(*self.consumption_range)
        self.water_level = max(0, self.water_level - consumption)
        self.total_consumed += consumption
        return consumption
    
    def add_water(self, amount):
        """Add water to sector (capped at max)"""
        old_level = self.water_level
        self.water_level = min(self.max_water, self.water_level + amount)
        actual_added = self.water_level - old_level
        self.total_allocated += actual_added
    
    def is_critical(self):
        """Check if water level is below risk threshold"""
        is_crit = self.water_level <= self.risk_threshold
        if is_crit:
            self.critical_warnings += 1
        return is_crit
    
    def is_empty(self):
        """Check if sector has run out of water"""
        return self.water_level <= 0


# ========================================
# EVENT CLASS
# ========================================
class Event:
    def __init__(self, sector, amount_needed):
        self.sector = sector
        self.amount_needed = amount_needed
        self.time_left = 8
        self.is_active = True
    
    def tick(self):
        """Countdown the timer"""
        if self.is_active:
            self.time_left -= 1
            if self.time_left <= 0:
                return True  # Event expired
        return False
    
    def resolve(self):
        """Mark event as resolved"""
        self.is_active = False


# ========================================
# CITY CLASS
# ========================================
class City:
    def __init__(self):
        self.tower_level = 1000
        self.max_tower = 1000
        self.refill_rate = 10
        
        # Create sectors
        self.sectors = {
            'Households': Sector('Households', (1, 7)),
            'Businesses': Sector('Businesses', (1, 5)),
            'Data Centers': Sector('Data Centers', (1, 10))
        }
    
    def refill_tower(self):
        """Refill water tower slowly"""
        self.tower_level = min(self.max_tower, self.tower_level + self.refill_rate)
    
    def allocate_water(self, sector_name, amount):
        """Allocate water from tower to sector"""
        if self.tower_level >= amount:
            self.tower_level -= amount
            self.sectors[sector_name].add_water(amount)
            return True
        return False
    
    def update_sectors(self):
        """Update all sectors (consumption)"""
        for sector in self.sectors.values():
            sector.consume()
    
    def check_lose_condition(self):
        """Check if any sector is empty"""
        for sector in self.sectors.values():
            if sector.is_empty():
                return True, sector.name
        return False, None


# ========================================
# GAME MANAGER
# ========================================
class GameManager:
    def __init__(self, ui):
        self.ui = ui
        self.city = City()
        self.active_event = None
        self.next_event_time = random.randint(10, 20)
        self.game_running = True
        self.start_time = time.time()
        self.win_time = 300  # 5 minutes in seconds
        
        # Statistics
        self.events_resolved = 0
        self.events_failed = 0
        self.total_allocations = 0
        self.difficulty_multiplier = 1.0
        self.ticks_survived = 0
    
    def game_tick(self):
        """Main game loop - called every second"""
        if not self.game_running:
            return
        
        self.ticks_survived += 1
        
        # Gradual difficulty increase
        if self.ticks_survived % 30 == 0:
            self.difficulty_multiplier += 0.05
        
        # Refill tower
        self.city.refill_tower()
        
        # Update sectors
        self.city.update_sectors()
        
        # Check for critical sectors
        for sector in self.city.sectors.values():
            if sector.is_critical() and not sector.is_empty():
                self.ui.log_message(f"⚠️ {sector.name} critically low!")
        
        # Update active event
        if self.active_event and self.active_event.is_active:
            expired = self.active_event.tick()
            if expired:
                self.handle_event_expiry()
        
        # Generate new event
        self.next_event_time -= 1
        if self.next_event_time <= 0 and (self.active_event is None or not self.active_event.is_active):
            self.generate_event()
            self.next_event_time = random.randint(10, 20)
        
        # Check lose condition
        lost, sector_name = self.city.check_lose_condition()
        if lost:
            self.game_over(sector_name)
            return
        
        # Check win condition
        elapsed_time = time.time() - self.start_time
        if elapsed_time >= self.win_time:
            self.game_won()
            return
        
        # Update UI
        self.ui.update_display()
        
        # Schedule next tick
        self.ui.root.after(1000, self.game_tick)
    
    def generate_event(self):
        """Generate a random urgent event"""
        sector_name = random.choice(list(self.city.sectors.keys()))
        amount = int(random.randint(20, 60) * self.difficulty_multiplier)
        self.active_event = Event(sector_name, amount)
        self.ui.log_message(f"🚨 URGENT: {sector_name} needs {amount} water in 8 seconds!")
    
    def handle_event_expiry(self):
        """Handle when event timer expires"""
        self.events_failed += 1
        sector = self.city.sectors[self.active_event.sector]
        sector.water_level = max(0, sector.water_level - 15)
        self.ui.log_message(f"❌ Event expired! {self.active_event.sector} lost 15 water")
        
        if sector.is_empty():
            self.game_over(self.active_event.sector)
        
        self.active_event.resolve()
    
    def resolve_event(self):
        """Player resolves the active event"""
        if self.active_event and self.active_event.is_active:
            amount = self.active_event.amount_needed
            if self.city.tower_level >= amount:
                self.city.allocate_water(self.active_event.sector, amount)
                self.events_resolved += 1
                self.total_allocations += 1
                self.ui.log_message(f"✅ Event resolved! {amount} water sent to {self.active_event.sector}")
                self.active_event.resolve()
            else:
                self.ui.log_message(f"❌ Not enough water in tower! Need {amount}, have {self.city.tower_level}")
    
    def get_statistics(self):
        """Get game statistics for end screen"""
        elapsed = time.time() - self.start_time
        return {
            'time_survived': elapsed,
            'events_resolved': self.events_resolved,
            'events_failed': self.events_failed,
            'total_allocations': self.total_allocations,
            'sectors': {name: {
                'total_consumed': sector.total_consumed,
                'total_allocated': sector.total_allocated,
                'critical_warnings': sector.critical_warnings,
                'final_level': sector.water_level
            } for name, sector in self.city.sectors.items()}
        }
    
    def game_over(self, sector_name):
        """Handle game over"""
        self.game_running = False
        self.ui.log_message(f"💀 GAME OVER: {sector_name} ran out of water!")
        stats = self.get_statistics()
        self.ui.show_end_screen(False, sector_name, stats)
    
    def game_won(self):
        """Handle victory"""
        self.game_running = False
        self.ui.log_message("🎉 VICTORY! You kept the city running for 5 minutes!")
        stats = self.get_statistics()
        self.ui.show_end_screen(True, None, stats)


# ========================================
# UI CLASS
# ========================================
class GameUI:
    def __init__(self, root):
        self.root = root
        self.root.title("WaterCycle - City Water Management Simulator")
        self.root.geometry("900x700")
        self.root.resizable(False, False)
        
        self.game_manager = None
        self.leaderboard_file = "watercycle_leaderboard.json"
        
        # Create UI elements
        self.create_ui()
    
    def create_ui(self):
        """Build the complete UI"""
        # Main container
        main_frame = tk.Frame(self.root, bg='#2c3e50')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Title
        title_label = tk.Label(main_frame, text="💧 WaterCycle - City Water Management", 
                               font=('Arial', 18, 'bold'), bg='#2c3e50', fg='white')
        title_label.pack(pady=10)
        
        # Timer display
        self.timer_label = tk.Label(main_frame, text="Time: 0:00 / 5:00", 
                                    font=('Arial', 12), bg='#2c3e50', fg='#ecf0f1')
        self.timer_label.pack()
        
        # Water tower section
        self.create_tower_section(main_frame)
        
        # Sectors section
        sectors_frame = tk.Frame(main_frame, bg='#2c3e50')
        sectors_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.sector_frames = {}
        sector_names = ['Households', 'Businesses', 'Data Centers']
        for i, name in enumerate(sector_names):
            self.sector_frames[name] = self.create_sector_ui(sectors_frame, name, i)
        
        # Event popup section
        self.create_event_section(main_frame)
        
        # Status log section
        self.create_log_section(main_frame)
    
    def create_tower_section(self, parent):
        """Create water tower display"""
        tower_frame = tk.LabelFrame(parent, text="💧 Water Tower", font=('Arial', 12, 'bold'),
                                    bg='#34495e', fg='white', padx=10, pady=10)
        tower_frame.pack(fill=tk.X, pady=5)
        
        self.tower_label = tk.Label(tower_frame, text="1000 / 1000", 
                                    font=('Arial', 14, 'bold'), bg='#34495e', fg='#3498db')
        self.tower_label.pack()
        
        self.tower_bar = ttk.Progressbar(tower_frame, length=800, mode='determinate', maximum=1000)
        self.tower_bar.pack(pady=5)
        self.tower_bar['value'] = 1000
    
    def create_sector_ui(self, parent, name, column):
        """Create UI for a single sector"""
        frame = tk.LabelFrame(parent, text=f"🏢 {name}", font=('Arial', 11, 'bold'),
                             bg='#34495e', fg='white', padx=10, pady=10)
        frame.grid(row=0, column=column, padx=5, sticky='nsew')
        parent.columnconfigure(column, weight=1)
        
        # Water level label
        water_label = tk.Label(frame, text="100 / 100", font=('Arial', 12), 
                              bg='#34495e', fg='#2ecc71')
        water_label.pack()
        
        # Progress bar
        progress = ttk.Progressbar(frame, length=200, mode='determinate', maximum=100)
        progress.pack(pady=5)
        progress['value'] = 100
        
        # Buttons
        btn_frame = tk.Frame(frame, bg='#34495e')
        btn_frame.pack(pady=5)
        
        btn_10 = tk.Button(btn_frame, text="+10", width=6, bg='#3498db', fg='white',
                          command=lambda: self.allocate_water(name, 10))
        btn_10.grid(row=0, column=0, padx=2)
        
        btn_25 = tk.Button(btn_frame, text="+25", width=6, bg='#3498db', fg='white',
                          command=lambda: self.allocate_water(name, 25))
        btn_25.grid(row=0, column=1, padx=2)
        
        btn_50 = tk.Button(btn_frame, text="+50", width=6, bg='#3498db', fg='white',
                          command=lambda: self.allocate_water(name, 50))
        btn_50.grid(row=0, column=2, padx=2)
        
        return {
            'frame': frame,
            'label': water_label,
            'bar': progress
        }
    
    def create_event_section(self, parent):
        """Create event popup display"""
        self.event_frame = tk.LabelFrame(parent, text="🚨 Urgent Event", font=('Arial', 11, 'bold'),
                                        bg='#e74c3c', fg='white', padx=10, pady=10)
        self.event_frame.pack(fill=tk.X, pady=5)
        
        self.event_label = tk.Label(self.event_frame, text="No active events", 
                                    font=('Arial', 11), bg='#e74c3c', fg='white')
        self.event_label.pack()
        
        self.event_button = tk.Button(self.event_frame, text="Allocate Now", 
                                      font=('Arial', 10, 'bold'),
                                      bg='#27ae60', fg='white', state=tk.DISABLED,
                                      command=self.resolve_event)
        self.event_button.pack(pady=5)
    
    def create_log_section(self, parent):
        """Create status log"""
        log_frame = tk.LabelFrame(parent, text="📋 Status Log", font=('Arial', 11, 'bold'),
                                 bg='#34495e', fg='white', padx=10, pady=10)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.log_text = tk.Text(log_frame, height=8, bg='#2c3e50', fg='#ecf0f1', 
                               font=('Courier', 9), wrap=tk.WORD)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = tk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)
        
        self.log_message("🎮 Game started! Keep all sectors supplied!")
    
    def allocate_water(self, sector_name, amount):
        """Player allocates water to a sector"""
        if self.game_manager and self.game_manager.game_running:
            success = self.game_manager.city.allocate_water(sector_name, amount)
            if success:
                self.game_manager.total_allocations += 1
                self.log_message(f"✓ Added {amount} water to {sector_name}")
            else:
                self.log_message(f"✗ Not enough water in tower!")
            self.update_display()
    
    def resolve_event(self):
        """Player resolves the active event"""
        if self.game_manager:
            self.game_manager.resolve_event()
    
    def update_display(self):
        """Update all UI elements"""
        if not self.game_manager:
            return
        
        city = self.game_manager.city
        
        # Update timer
        elapsed = time.time() - self.game_manager.start_time
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        self.timer_label.config(text=f"Time: {minutes}:{seconds:02d} / 5:00")
        
        # Update tower
        self.tower_label.config(text=f"{city.tower_level} / {city.max_tower}")
        self.tower_bar['value'] = city.tower_level
        
        # Update sectors
        for name, sector in city.sectors.items():
            ui = self.sector_frames[name]
            ui['label'].config(text=f"{sector.water_level} / {sector.max_water}")
            ui['bar']['value'] = sector.water_level
            
            # Color coding
            if sector.water_level <= 20:
                ui['label'].config(fg='#e74c3c')  # Red
            elif sector.water_level <= 50:
                ui['label'].config(fg='#f39c12')  # Orange
            else:
                ui['label'].config(fg='#2ecc71')  # Green
        
        # Update event
        event = self.game_manager.active_event
        if event and event.is_active:
            self.event_label.config(
                text=f"{event.sector} needs {event.amount_needed} water!\nTime left: {event.time_left}s"
            )
            self.event_button.config(state=tk.NORMAL)
        else:
            self.event_label.config(text="No active events")
            self.event_button.config(state=tk.DISABLED)
    
    def log_message(self, message):
        """Add message to status log"""
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
    
    def calculate_score(self, stats, won):
        """Calculate final score based on performance"""
        score = 0
        score += int(stats['time_survived'] * 100)
        if won:
            score += 50000
        score += stats['events_resolved'] * 1000
        score -= stats['events_failed'] * 500
        for sector_stats in stats['sectors'].values():
            score += sector_stats['final_level'] * 10
            score -= sector_stats['critical_warnings'] * 100
        return max(0, score)
    
    def load_leaderboard(self):
        """Load leaderboard from file"""
        if os.path.exists(self.leaderboard_file):
            try:
                with open(self.leaderboard_file, 'r') as f:
                    return json.load(f)
            except:
                return []
        return []
    
    def save_leaderboard(self, leaderboard):
        """Save leaderboard to file"""
        try:
            with open(self.leaderboard_file, 'w') as f:
                json.dump(leaderboard, f, indent=2)
        except:
            pass
    
    def add_to_leaderboard(self, score, won, stats):
        """Add current game to leaderboard"""
        leaderboard = self.load_leaderboard()
        
        minutes = int(stats['time_survived'] // 60)
        seconds = int(stats['time_survived'] % 60)
        
        entry = {
            'score': score,
            'won': won,
            'time': f"{minutes}m {seconds}s",
            'time_seconds': stats['time_survived'],
            'events_resolved': stats['events_resolved'],
            'events_failed': stats['events_failed'],
            'date': datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        
        leaderboard.append(entry)
        leaderboard.sort(key=lambda x: x['score'], reverse=True)
        leaderboard = leaderboard[:10]
        
        self.save_leaderboard(leaderboard)
        return leaderboard
    
    def show_leaderboard(self, parent, current_score, won):
        """Display leaderboard in a tab"""
        tk.Label(parent, text="🏆 Top 10 High Scores", font=('Arial', 16, 'bold'),
                bg='#34495e', fg='#f1c40f').pack(pady=15)
        
        canvas = tk.Canvas(parent, bg='#34495e', highlightthickness=0)
        scrollbar = tk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#34495e')
        
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        scrollbar.pack(side="right", fill="y")
        
        leaderboard = self.load_leaderboard()
        
        if not leaderboard:
            tk.Label(scrollable_frame, text="No scores yet! Be the first!",
                    font=('Arial', 12), bg='#34495e', fg='#ecf0f1').pack(pady=20)
        else:
            header_frame = tk.Frame(scrollable_frame, bg='#2c3e50', padx=10, pady=5)
            header_frame.pack(fill=tk.X, pady=(0, 10), padx=10)
            
            tk.Label(header_frame, text="Rank", font=('Arial', 10, 'bold'),
                    bg='#2c3e50', fg='#ecf0f1', width=6).grid(row=0, column=0, padx=5)
            tk.Label(header_frame, text="Score", font=('Arial', 10, 'bold'),
                    bg='#2c3e50', fg='#ecf0f1', width=12).grid(row=0, column=1, padx=5)
            tk.Label(header_frame, text="Time", font=('Arial', 10, 'bold'),
                    bg='#2c3e50', fg='#ecf0f1', width=10).grid(row=0, column=2, padx=5)
            tk.Label(header_frame, text="Events", font=('Arial', 10, 'bold'),
                    bg='#2c3e50', fg='#ecf0f1', width=10).grid(row=0, column=3, padx=5)
            tk.Label(header_frame, text="Date", font=('Arial', 10, 'bold'),
                    bg='#2c3e50', fg='#ecf0f1', width=15).grid(row=0, column=4, padx=5)
            
            for i, entry in enumerate(leaderboard, 1):
                is_current = (entry['score'] == current_score and i == 1 and entry == leaderboard[0])
                bg_color = '#27ae60' if is_current else '#34495e'
                
                entry_frame = tk.Frame(scrollable_frame, bg=bg_color, padx=10, pady=8)
                entry_frame.pack(fill=tk.X, pady=3, padx=10)
                
                rank_text = f"🥇 #{i}" if i == 1 else f"🥈 #{i}" if i == 2 else f"🥉 #{i}" if i == 3 else f"#{i}"
                tk.Label(entry_frame, text=rank_text, font=('Arial', 11, 'bold'),
                        bg=bg_color, fg='#f1c40f' if i <= 3 else '#ecf0f1', width=6).grid(row=0, column=0, padx=5)
                
                score_text = f"{entry['score']:,}"
                tk.Label(entry_frame, text=score_text, font=('Arial', 10),
                        bg=bg_color, fg='#ecf0f1', width=12).grid(row=0, column=1, padx=5)
                
                result_icon = "🎉" if entry.get('won', False) else "💀"
                time_text = f"{result_icon} {entry['time']}"
                tk.Label(entry_frame, text=time_text, font=('Arial', 10),
                        bg=bg_color, fg='#ecf0f1', width=10).grid(row=0, column=2, padx=5)
                
                events_text = f"✓{entry['events_resolved']} ✗{entry['events_failed']}"
                tk.Label(entry_frame, text=events_text, font=('Arial', 10),
                        bg=bg_color, fg='#ecf0f1', width=10).grid(row=0, column=3, padx=5)
                
                tk.Label(entry_frame, text=entry['date'], font=('Arial', 9),
                        bg=bg_color, fg='#95a5a6', width=15).grid(row=0, column=4, padx=5)
                
                if is_current:
                    tk.Label(entry_frame, text="← NEW!", font=('Arial', 10, 'bold'),
                            bg=bg_color, fg='#f1c40f').grid(row=0, column=5, padx=10)
    
    def show_end_screen(self, won, failed_sector, stats):
        """Display detailed end screen with scrollable stats"""
        end_window = tk.Toplevel(self.root)
        end_window.title("Game Over" if not won else "Victory!")
        end_window.geometry("700x650")
        end_window.configure(bg='#2c3e50')
        end_window.grab_set()
        
        title_text = "🎉 VICTORY!" if won else "💀 GAME OVER"
        title_color = '#27ae60' if won else '#e74c3c'
        
        title = tk.Label(end_window, text=title_text, font=('Arial', 24, 'bold'),
                        bg='#2c3e50', fg=title_color)
        title.pack(pady=15)
        
        if not won:
            result_msg = f"⚠️ {failed_sector} ran out of water"
            tk.Label(end_window, text=result_msg, font=('Arial', 14),
                    bg='#2c3e50', fg='#e74c3c').pack(pady=5)
        else:
            result_msg = "You successfully managed the city!"
            tk.Label(end_window, text=result_msg, font=('Arial', 14),
                    bg='#2c3e50', fg='#27ae60').pack(pady=5)
        
        notebook = ttk.Notebook(end_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        stats_tab = tk.Frame(notebook, bg='#34495e')
        notebook.add(stats_tab, text="📊 Your Stats")
        
        canvas = tk.Canvas(stats_tab, bg='#34495e', highlightthickness=0)
        scrollbar = tk.Scrollbar(stats_tab, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#34495e')
        
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        scrollbar.pack(side="right", fill="y")
        
        minutes = int(stats['time_survived'] // 60)
        seconds = int(stats['time_survived'] % 60)
        
        tk.Label(scrollable_frame, text="⏱️ Performance Summary", font=('Arial', 16, 'bold'),
                bg='#34495e', fg='white').pack(pady=10)
        
        score = self.calculate_score(stats, won)
        tk.Label(scrollable_frame, text=f"SCORE: {score:,}", 
                font=('Arial', 14, 'bold'), bg='#34495e', fg='#f1c40f').pack(pady=5)
        
        tk.Label(scrollable_frame, text=f"Time Survived: {minutes}m {seconds}s", 
                font=('Arial', 12), bg='#34495e', fg='#3498db').pack(pady=5)
        
        tk.Label(scrollable_frame, text=f"Events Resolved: {stats['events_resolved']}", 
                font=('Arial', 12), bg='#34495e', fg='#2ecc71').pack(pady=3)
        
        tk.Label(scrollable_frame, text=f"Events Failed: {stats['events_failed']}", 
                font=('Arial', 12), bg='#34495e', fg='#e74c3c').pack(pady=3)
        
        tk.Label(scrollable_frame, text=f"Total Allocations: {stats['total_allocations']}", 
                font=('Arial', 12), bg='#34495e', fg='#ecf0f1').pack(pady=3)
        
        tk.Label(scrollable_frame, text="\n📊 Sector Statistics", font=('Arial', 14, 'bold'),
                bg='#34495e', fg='white').pack(pady=10)
        
        for sector_name, sector_stats in stats['sectors'].items():
            sector_frame = tk.Frame(scrollable_frame, bg='#2c3e50', padx=10, pady=8)
            sector_frame.pack(fill=tk.X, pady=5, padx=10)
            
            name_color = '#e74c3c' if sector_name == failed_sector else '#ecf0f1'
            
            tk.Label(sector_frame, text=f"🏢 {sector_name}", font=('Arial', 11, 'bold'),
                    bg='#2c3e50', fg=name_color).pack(anchor='w')
            
            tk.Label(sector_frame, text=f"  Final Level: {sector_stats['final_level']}/100",
                    font=('Arial', 10), bg='#2c3e50', fg='#ecf0f1').pack(anchor='w')
            
            tk.Label(sector_frame, text=f"  Total Consumed: {sector_stats['total_consumed']}",
                    font=('Arial', 10), bg='#2c3e50', fg='#ecf0f1').pack(anchor='w')
            
            tk.Label(sector_frame, text=f"  Total Allocated: {sector_stats['total_allocated']}",
                    font=('Arial', 10), bg='#2c3e50', fg='#ecf0f1').pack(anchor='w')
            
            tk.Label(sector_frame, text=f"  Critical Warnings: {sector_stats['critical_warnings']}",
                    font=('Arial', 10), bg='#2c3e50', fg='#f39c12').pack(anchor='w')
        
        leaderboard_tab = tk.Frame(notebook, bg='#34495e')
        notebook.add(leaderboard_tab, text="🏆 Leaderboard")
        
        self.add_to_leaderboard(score, won, stats)
        self.show_leaderboard(leaderboard_tab, score, won)
        
        btn_frame = tk.Frame(end_window, bg='#2c3e50')
        btn_frame.pack(pady=15)
        
        tk.Button(btn_frame, text="Play Again", font=('Arial', 12, 'bold'),
                 bg='#27ae60', fg='white', width=15, height=2,
                 command=lambda: self.restart_game(end_window)).pack(side=tk.LEFT, padx=10)
        
        tk.Button(btn_frame, text="Quit", font=('Arial', 12, 'bold'),
                 bg='#e74c3c', fg='white', width=15, height=2,
                 command=self.root.quit).pack(side=tk.LEFT, padx=10)
    
    def restart_game(self, end_window):
        """Restart the game"""
        end_window.destroy()
        self.log_text.delete(1.0, tk.END)
        self.log_message("🎮 Game restarted! Keep all sectors supplied!")
        self.start_game()
    
    def start_game(self):
        """Initialize and start the game"""
        self.game_manager = GameManager(self)
        self.game_manager.game_tick()


# ========================================
# MAIN ENTRY POINT
# ========================================
def main():
    root = tk.Tk()
    ui = GameUI(root)
    ui.start_game()
    root.mainloop()


if __name__ == "__main__":
    main()