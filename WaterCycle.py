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
from tkinter import ttk, messagebox
import random
import time


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
    
    def consume(self):
        """Consume random amount of water based on consumption range"""
        consumption = random.randint(*self.consumption_range)
        self.water_level = max(0, self.water_level - consumption)
        return consumption
    
    def add_water(self, amount):
        """Add water to sector (capped at max)"""
        self.water_level = min(self.max_water, self.water_level + amount)
    
    def is_critical(self):
        """Check if water level is below risk threshold"""
        return self.water_level <= self.risk_threshold
    
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
        self.refill_rate = 8
        
        # Create sectors
        self.sectors = {
            'Households': Sector('Households', (1, 7)),
            'Businesses': Sector('Businesses', (1, 5)),
            'Data Centers': Sector('Data Centers', (1, 10)) # Extreme fluctuating consumption, can be low or extremely high.
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
    
    def game_tick(self):
        """Main game loop - called every second"""
        if not self.game_running:
            return
        
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
        amount = random.randint(20, 60)
        self.active_event = Event(sector_name, amount)
        self.ui.log_message(f"🚨 URGENT: {sector_name} needs {amount} water in 8 seconds!")
    
    def handle_event_expiry(self):
        """Handle when event timer expires"""
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
                self.ui.log_message(f"✅ Event resolved! {amount} water sent to {self.active_event.sector}")
                self.active_event.resolve()
            else:
                self.ui.log_message(f"❌ Not enough water in tower! Need {amount}, have {self.city.tower_level}")
    
    def game_over(self, sector_name):
        """Handle game over"""
        self.game_running = False
        self.ui.log_message(f"💀 GAME OVER: {sector_name} ran out of water!")
        messagebox.showerror("Game Over", f"{sector_name} ran out of water!\n\nYou lasted {int(time.time() - self.start_time)} seconds.")
        self.ui.root.quit()
    
    def game_won(self):
        """Handle victory"""
        self.game_running = False
        self.ui.log_message("🎉 VICTORY! You kept the city running for 5 minutes!")
        messagebox.showinfo("Victory!", "Congratulations! You successfully managed the city's water for 5 minutes!")
        self.ui.root.quit()


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
                             bg='#34495e', fg='grey', padx=10, pady=10)
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
        #Add message to status log
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)
    
    def start_game(self):
        # Initialize and start the game
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