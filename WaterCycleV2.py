"""
## Acknowledgments & Inspirations

This WaterCycle game was inspired by patterns and techniques from several 
open-source Python/Tkinter projects:

### Game State Management
- **xyzen/xyGames** - Adapted the Game class state management pattern (NEW_GAME, 
  ACTIVE, PAUSED, GAME_OVER, GAME_WON) and score tracking system. Extended with 
  resource-specific state (water levels, event timers, win conditions).
  
- **akmalmzamri/python-knife-hit** - Studied the GameManager class architecture 
  with threading for delayed game triggers and the separation of game logic from 
  UI rendering.

### UI & Visual Elements
- **tisnik/presentations** (Python_GUI/Tkinter/53_menu_images.py) - Referenced 
  PhotoImage loading patterns for icons in menus. Applied similar concepts using 
  emoji/unicode symbols throughout the interface.
  
- **pythonprogramming.altervista.org** - Studied toolbar button creation with 
  icons and compound layouts. Adapted for sector allocation buttons with lambda 
  command patterns.

- **TomSchimansky/CustomTkinter** - Reviewed ttk.Progressbar implementation patterns 
  for multiple resource bars. Adapted determinate mode progress bars for water 
  level visualization across sectors and the central tower.

### Game Loop Architecture
- **Kent D. Lee's Game Development Tutorial** - Adapted the `root.after()` 
  recursive timer pattern and datetime-based elapsed time tracking for the 
  5-minute win condition.
  
- **Deformater/tkinter_doom** - Referenced dependency injection pattern (passing 
  UI components to game logic classes) and event binding structure for clean 
  separation between game state and rendering.

### Data Persistence & Scoring
- **Stack Overflow: Python Leaderboard Systems** - Adapted JSON-based leaderboard 
  storage patterns with sorting and top-N filtering. Implemented persistent score 
  tracking with timestamp metadata and win/loss statistics.

- **codeisconquer/python-tkinter-gui-json-gen** - Studied JSON file handling 
  patterns for save/load operations. Applied try-catch error handling for graceful 
  degradation when leaderboard file is missing or corrupted.

### Scrollable UI Components  
- **novel-yet-trivial/VerticalScrolledFrame** (GitHub Gist) - Reviewed scrollable 
  frame implementation using Canvas and Scrollbar widgets. Applied this pattern 
  for the scrollable statistics display and leaderboard tabs in the end-game screen.

- **muhammeteminturgut/ttkScrollableNotebook** - Studied tabbed interface patterns 
  with ttk.Notebook for organizing end-game content (Statistics vs Leaderboard views).

### Color Coding & Visual Feedback
- **Stack Overflow: Dynamic Widget Styling** - Adapted conditional color changes 
  based on state (green/orange/red for water levels). Applied to both label text 
  and visual indicators for immediate player feedback.

### Architecture Patterns
- **Dictionary-Based Widget Management** - Storing UI element references in 
  dictionaries (`self.sector_frames`) for efficient bulk updates during game loop.
  
- **Callback Pattern with Lambda** - Using lambda functions to pass parameters to 
  button commands while maintaining closure scope for sector names and amounts.

All code was written from scratch implementing unique water resource management 
mechanics. The above projects served as reference implementations and design 
inspiration rather than direct code sources.
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
# Represents a district in the city that needs water (like Households, Businesses, etc.)
# ========================================
class Sector:
    def __init__(self, name, consumption_range, risk_threshold=20):
        """
        Initialize a sector with water storage and consumption characteristics.
        
        Args:
            name: The name of the sector (e.g., "Households")
            consumption_range: Tuple of (min, max) water consumed per tick
            risk_threshold: Water level below which sector is considered critical (default 20)
        """
        self.name = name
        self.water_level = 100  # Current water available in this sector
        self.max_water = 100    # Maximum water capacity
        self.consumption_range = consumption_range  # How much water this sector uses per tick
        self.risk_threshold = risk_threshold  # Level at which sector becomes critical
        
        # Statistics tracking
        self.total_consumed = 0      # Total water used over game
        self.total_allocated = 0     # Total water given to this sector
        self.critical_warnings = 0   # Number of times sector went critical
    
    def consume(self):
        """
        Consume a random amount of water based on the sector's consumption range.
        This happens every game tick to simulate ongoing water usage.
        
        Returns:
            int: The amount of water consumed this tick
        """
        consumption = random.randint(*self.consumption_range)
        self.water_level = max(0, self.water_level - consumption)  # Don't go below 0
        self.total_consumed += consumption
        return consumption
    
    def add_water(self, amount):
        """
        Add water to this sector from the water tower.
        Water is capped at the sector's maximum capacity.
        
        Args:
            amount: Amount of water to add
        """
        old_level = self.water_level
        self.water_level = min(self.max_water, self.water_level + amount)  # Cap at max
        actual_added = self.water_level - old_level  # Calculate overflow
        self.total_allocated += actual_added
    
    def is_critical(self):
        """
        Check if the sector's water level is below the risk threshold.
        Increments warning counter if critical.
        
        Returns:
            bool: True if sector is critical, False otherwise
        """
        is_crit = self.water_level <= self.risk_threshold
        if is_crit:
            self.critical_warnings += 1
        return is_crit
    
    def is_empty(self):
        """
        Check if the sector has completely run out of water.
        This triggers a game over condition.
        
        Returns:
            bool: True if water level is 0 or below
        """
        return self.water_level <= 0


# ========================================
# EVENT CLASS
# Represents an urgent water request from a sector with a countdown timer
# ========================================
class Event:
    def __init__(self, sector, amount_needed):
        """
        Create an urgent event requiring immediate water allocation.
        
        Args:
            sector: Name of the sector requesting water
            amount_needed: Amount of water required to resolve the event
        """
        self.sector = sector
        self.amount_needed = amount_needed
        self.time_left = 8      # Player has 8 seconds to respond
        self.is_active = True   # Whether this event is still pending
    
    def tick(self):
        """
        Countdown the event timer by one second.
        Called each game tick.
        
        Returns:
            bool: True if event has expired (time ran out), False otherwise
        """
        if self.is_active:
            self.time_left -= 1
            if self.time_left <= 0:
                return True  # Event expired - player failed to respond in time
        return False
    
    def resolve(self):
        """
        Mark the event as resolved (either completed or expired).
        Prevents further timer countdown.
        """
        self.is_active = False


# ========================================
# CITY CLASS
# Manages the water tower and all sectors in the city
# ========================================
class City:
    def __init__(self):
        """
        Initialize the city with a water tower and three sectors.
        The water tower is the central resource that refills slowly.
        """
        self.tower_level = 1000  # Current water in the central tower
        self.max_tower = 1000    # Maximum tower capacity
        self.refill_rate = 16    # Water added to tower per tick (passive income)
        
        # Create the three sectors with different consumption patterns
        # Tuple format: (min_consumption, max_consumption)
        self.sectors = {
            'Households': Sector('Households', (1, 7)),      # Low consumption
            'Businesses': Sector('Businesses', (2, 8)),      # Medium consumption
            'Data Centers': Sector('Data Centers', (3, 10))  # High consumption
        }
    
    def refill_tower(self):
        """
        Slowly refill the water tower each tick.
        This is the player's passive water income.
        """
        self.tower_level = min(self.max_tower, self.tower_level + self.refill_rate)
    
    def allocate_water(self, sector_name, amount):
        """
        Transfer water from the tower to a specific sector.
        Only works if tower has enough water.
        
        Args:
            sector_name: Name of sector to receive water
            amount: Amount of water to transfer
            
        Returns:
            bool: True if allocation succeeded, False if not enough water in tower
        """
        if self.tower_level >= amount:
            self.tower_level -= amount
            self.sectors[sector_name].add_water(amount)
            return True
        return False
    
    def update_sectors(self):
        """
        Update all sectors by having them consume water.
        Called once per game tick.
        """
        for sector in self.sectors.values():
            sector.consume()
    
    def check_lose_condition(self):
        """
        Check if any sector has run out of water completely.
        This causes the game to end.
        
        Returns:
            tuple: (has_lost, sector_name) - True and sector name if lost, False and None otherwise
        """
        for sector in self.sectors.values():
            if sector.is_empty():
                return True, sector.name
        return False, None


# ========================================
# GAME MANAGER
# Controls the main game loop, events, difficulty, and win/lose conditions
# ========================================
class GameManager:
    def __init__(self, ui):
        """
        Initialize the game manager with all game state.
        
        Args:
            ui: Reference to the UI class for display updates
        """
        self.ui = ui
        self.city = City()
        self.active_event = None             # Currently active urgent event
        self.next_event_time = random.randint(10, 20)  # Ticks until next event spawns
        self.game_running = True
        self.start_time = time.time()
        self.win_time = 300                  # Win after 5 minutes (300 seconds)
        
        # Statistics tracking
        self.events_resolved = 0             # Events player successfully handled
        self.events_failed = 0               # Events that expired
        self.total_allocations = 0           # Total water allocations made
        self.difficulty_multiplier = 1.0     # Increases over time
        self.ticks_survived = 0              # Total game ticks (seconds)
    
    def game_tick(self):
        """
        Main game loop - executes once per second.
        Handles all game updates: refilling, consumption, events, and conditions.
        """
        if not self.game_running:
            return
        
        self.ticks_survived += 1
        
        # Gradually increase difficulty every 30 seconds
        if self.ticks_survived % 30 == 0:
            self.difficulty_multiplier += 0.05
        
        # Refill the water tower (passive income)
        self.city.refill_tower()
        
        # All sectors consume water
        self.city.update_sectors()
        
        # Check for sectors in critical condition and warn player
        for sector in self.city.sectors.values():
            if sector.is_critical() and not sector.is_empty():
                self.ui.log_message(f"⚠️ {sector.name} critically low!")
        
        # Update active event timer
        if self.active_event and self.active_event.is_active:
            expired = self.active_event.tick()
            if expired:
                self.handle_event_expiry()
        
        # Countdown to next event and generate if time is up
        self.next_event_time -= 1
        if self.next_event_time <= 0 and (self.active_event is None or not self.active_event.is_active):
            self.generate_event()
            self.next_event_time = random.randint(10, 20)  # Reset timer
        
        # Check if player has lost (any sector empty)
        lost, sector_name = self.city.check_lose_condition()
        if lost:
            self.game_over(sector_name)
            return
        
        # Check if player has won (survived 5 minutes)
        elapsed_time = time.time() - self.start_time
        if elapsed_time >= self.win_time:
            self.game_won()
            return
        
        # Update the UI with current game state
        self.ui.update_display()
        
        # Schedule the next game tick in 1 second
        self.ui.root.after(1000, self.game_tick)
    
    def generate_event(self):
        """
        Generate a random urgent event for a sector.
        Amount needed scales with difficulty multiplier.
        """
        sector_name = random.choice(list(self.city.sectors.keys()))
        amount = int(random.randint(20, 60) * self.difficulty_multiplier)
        self.active_event = Event(sector_name, amount)
        self.ui.log_message(f"🚨 URGENT: {sector_name} needs {amount} water in 8 seconds!")
    
    def handle_event_expiry(self):
        """
        Handle when player fails to resolve an event in time.
        Penalizes the sector with water loss and may cause game over.
        """
        self.events_failed += 1
        sector = self.city.sectors[self.active_event.sector]
        sector.water_level = max(0, sector.water_level - 15)  # Penalty: lose 15 water
        self.ui.log_message(f"❌ Event expired! {self.active_event.sector} lost 15 water")
        
        # Check if penalty caused sector to empty
        if sector.is_empty():
            self.game_over(self.active_event.sector)
        
        self.active_event.resolve()
    
    def resolve_event(self):
        """
        Player attempts to resolve the active event by allocating water.
        Only succeeds if tower has enough water available.
        """
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
        """
        Compile all game statistics for the end screen.
        
        Returns:
            dict: Complete statistics including time, events, and sector data
        """
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
        """
        Handle game loss condition.
        Stops game loop and displays end screen with statistics.
        
        Args:
            sector_name: Name of the sector that ran out of water
        """
        self.game_running = False
        self.ui.log_message(f"💀 GAME OVER: {sector_name} ran out of water!")
        stats = self.get_statistics()
        self.ui.show_end_screen(False, sector_name, stats)
    
    def game_won(self):
        """
        Handle victory condition.
        Stops game loop and displays victory screen with statistics.
        """
        self.game_running = False
        self.ui.log_message("🎉 VICTORY! You kept the city running for 5 minutes!")
        stats = self.get_statistics()
        self.ui.show_end_screen(True, None, stats)
# ========================================
# UI CLASS
# Manages all visual elements and user interactions for the game
# Built using tkinter for the graphical interface
# ========================================
class GameUI:
    def __init__(self, root):
        """
        Initialize the game UI with the main window.
        
        Args:
            root: The tkinter root window object
        """
        self.root = root
        self.root.title("WaterCycle - City Water Management Simulator")
        self.root.geometry("900x700")  # Set window size
        self.root.resizable(False, False)  # Prevent window resizing
        
        self.game_manager = None  # Will hold reference to GameManager once game starts
        self.leaderboard_file = "watercycle_leaderboard.json"  # File to store high scores
        
        # Build all UI components
        self.create_ui()
    
    def create_ui(self):
        """
        Build the complete user interface layout.
        Creates all frames, labels, buttons, and other UI elements.
        """
        # Main container frame with dark blue-gray background
        main_frame = tk.Frame(self.root, bg='#2c3e50')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Game title at the top
        title_label = tk.Label(main_frame, text="💧 WaterCycle - City Water Management", 
                               font=('Arial', 18, 'bold'), bg='#2c3e50', fg='white')
        title_label.pack(pady=10)
        
        # Timer showing elapsed time and target time
        self.timer_label = tk.Label(main_frame, text="Time: 0:00 / 5:00", 
                                    font=('Arial', 12), bg='#2c3e50', fg='#ecf0f1')
        self.timer_label.pack()
        
        # Water tower display (central resource)
        self.create_tower_section(main_frame)
        
        # Container for the three sector displays
        sectors_frame = tk.Frame(main_frame, bg='#2c3e50')
        sectors_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Create UI for each sector (Households, Businesses, Data Centers)
        self.sector_frames = {}  # Store references to sector UI elements
        sector_names = ['Households', 'Businesses', 'Data Centers']
        for i, name in enumerate(sector_names):
            self.sector_frames[name] = self.create_sector_ui(sectors_frame, name, i)
        
        # Event popup section (urgent requests)
        self.create_event_section(main_frame)
        
        # Status log showing game messages
        self.create_log_section(main_frame)
    
    def create_tower_section(self, parent):
        """
        Create the water tower display showing central resource.
        
        Args:
            parent: Parent frame to attach this section to
        """
        # Frame with border and title
        tower_frame = tk.LabelFrame(parent, text="💧 Water Tower", font=('Arial', 12, 'bold'),
                                    bg='#34495e', fg='white', padx=10, pady=10)
        tower_frame.pack(fill=tk.X, pady=5)
        
        # Label showing current/max water in tower
        self.tower_label = tk.Label(tower_frame, text="1000 / 1000", 
                                    font=('Arial', 14, 'bold'), bg='#34495e', fg='#3498db')
        self.tower_label.pack()
        
        # Progress bar visualizing tower water level
        self.tower_bar = ttk.Progressbar(tower_frame, length=800, mode='determinate', maximum=1000)
        self.tower_bar.pack(pady=5)
        self.tower_bar['value'] = 1000  # Start full
    
    def create_sector_ui(self, parent, name, column):
        """
        Create UI elements for a single sector.
        Each sector has a water level display and allocation buttons.
        
        Args:
            parent: Parent frame to attach this section to
            name: Name of the sector (e.g., "Households")
            column: Grid column position (0, 1, or 2)
            
        Returns:
            dict: References to the sector's UI elements (frame, label, progress bar)
        """
        # Frame with sector name as title
        frame = tk.LabelFrame(parent, text=f"🏢 {name}", font=('Arial', 11, 'bold'),
                             bg='#34495e', fg='white', padx=10, pady=10)
        frame.grid(row=0, column=column, padx=5, sticky='nsew')
        parent.columnconfigure(column, weight=1)  # Equal column widths
        
        # Water level label (current/max)
        water_label = tk.Label(frame, text="100 / 100", font=('Arial', 12), 
                              bg='#34495e', fg='#2ecc71')
        water_label.pack()
        
        # Progress bar showing water level visually
        progress = ttk.Progressbar(frame, length=200, mode='determinate', maximum=100)
        progress.pack(pady=5)
        progress['value'] = 100  # Start full
        
        # Container for allocation buttons
        btn_frame = tk.Frame(frame, bg='#34495e')
        btn_frame.pack(pady=5)
        
        # Three buttons to allocate different amounts of water
        # Using lambda to pass sector name and amount to allocate_water method
        btn_10 = tk.Button(btn_frame, text="+10", width=6, bg='#3498db', fg='white',
                          command=lambda: self.allocate_water(name, 10))
        btn_10.grid(row=0, column=0, padx=2)
        
        btn_25 = tk.Button(btn_frame, text="+25", width=6, bg='#3498db', fg='white',
                          command=lambda: self.allocate_water(name, 25))
        btn_25.grid(row=0, column=1, padx=2)
        
        btn_50 = tk.Button(btn_frame, text="+50", width=6, bg='#3498db', fg='white',
                          command=lambda: self.allocate_water(name, 50))
        btn_50.grid(row=0, column=2, padx=2)
        
        # Return references to UI elements for later updates
        return {
            'frame': frame,
            'label': water_label,
            'bar': progress
        }
    
    def create_event_section(self, parent):
        """
        Create the urgent event display section.
        Shows active events that require immediate player response.
        
        Args:
            parent: Parent frame to attach this section to
        """
        # Red frame to draw attention to urgent events
        self.event_frame = tk.LabelFrame(parent, text="🚨 Urgent Event", font=('Arial', 11, 'bold'),
                                        bg='#e74c3c', fg='white', padx=10, pady=10)
        self.event_frame.pack(fill=tk.X, pady=5)
        
        # Label showing event details (sector, amount, time)
        self.event_label = tk.Label(self.event_frame, text="No active events", 
                                    font=('Arial', 11), bg='#e74c3c', fg='white')
        self.event_label.pack()
        
        # Button to resolve the event (disabled when no event active)
        self.event_button = tk.Button(self.event_frame, text="Allocate Now", 
                                      font=('Arial', 10, 'bold'),
                                      bg='#27ae60', fg='white', state=tk.DISABLED,
                                      command=self.resolve_event)
        self.event_button.pack(pady=5)
    
    def create_log_section(self, parent):
        """
        Create the status log that shows game messages.
        Displays what's happening in the game (allocations, warnings, events).
        
        Args:
            parent: Parent frame to attach this section to
        """
        # Frame with title
        log_frame = tk.LabelFrame(parent, text="📋 Status Log", font=('Arial', 11, 'bold'),
                                 bg='#34495e', fg='white', padx=10, pady=10)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Text widget for displaying messages
        self.log_text = tk.Text(log_frame, height=8, bg='#2c3e50', fg='#ecf0f1', 
                               font=('Courier', 9), wrap=tk.WORD)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Scrollbar for when there are many messages
        scrollbar = tk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)
        
        # Add initial welcome message
        self.log_message("🎮 Game started! Keep all sectors supplied!")
    
    def allocate_water(self, sector_name, amount):
        """
        Handle player clicking a water allocation button.
        Attempts to send water from tower to the specified sector.
        
        Args:
            sector_name: Name of sector to receive water
            amount: Amount of water to allocate
        """
        if self.game_manager and self.game_manager.game_running:
            # Try to allocate water (will fail if tower doesn't have enough)
            success = self.game_manager.city.allocate_water(sector_name, amount)
            if success:
                self.game_manager.total_allocations += 1
                self.log_message(f"✓ Added {amount} water to {sector_name}")
            else:
                self.log_message(f"✗ Not enough water in tower!")
            # Update display to show new water levels
            self.update_display()
    
    def resolve_event(self):
        """
        Handle player clicking the "Allocate Now" button for an event.
        Delegates to game manager to handle the event resolution.
        """
        if self.game_manager:
            self.game_manager.resolve_event()
    
    def update_display(self):
        """
        Update all UI elements to reflect current game state.
        Called every game tick and after player actions.
        Updates: timer, tower level, sector levels, event status.
        """
        if not self.game_manager:
            return
        
        city = self.game_manager.city
        
        # Update timer display (minutes:seconds format)
        elapsed = time.time() - self.game_manager.start_time
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        self.timer_label.config(text=f"Time: {minutes}:{seconds:02d} / 5:00")
        
        # Update water tower display
        self.tower_label.config(text=f"{city.tower_level} / {city.max_tower}")
        self.tower_bar['value'] = city.tower_level
        
        # Update each sector's display
        for name, sector in city.sectors.items():
            ui = self.sector_frames[name]
            ui['label'].config(text=f"{sector.water_level} / {sector.max_water}")
            ui['bar']['value'] = sector.water_level
            
            # Color coding based on water level (red=critical, orange=warning, green=good)
            if sector.water_level <= 20:
                ui['label'].config(fg='#e74c3c')  # Red - critical
            elif sector.water_level <= 50:
                ui['label'].config(fg='#f39c12')  # Orange - warning
            else:
                ui['label'].config(fg='#2ecc71')  # Green - healthy
        
        # Update event display
        event = self.game_manager.active_event
        if event and event.is_active:
            # Show event details with countdown
            self.event_label.config(
                text=f"{event.sector} needs {event.amount_needed} water!\nTime left: {event.time_left}s"
            )
            self.event_button.config(state=tk.NORMAL)  # Enable button
        else:
            # No active event
            self.event_label.config(text="No active events")
            self.event_button.config(state=tk.DISABLED)  # Disable button
    
    def log_message(self, message):
        """
        Add a message to the status log.
        Automatically scrolls to show the newest message.
        
        Args:
            message: Text message to display
        """
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)  # Auto-scroll to bottom
    
    def calculate_score(self, stats, won):
        """
        Calculate the player's final score based on performance.
        
        Scoring formula:
        - Base: time survived × 100
        - Bonus: +50,000 for winning
        - +1,000 per event resolved
        - -500 per event failed
        - +10 per final water unit in sectors
        - -100 per critical warning
        
        Args:
            stats: Dictionary of game statistics
            won: Boolean indicating if player won
            
        Returns:
            int: Final score (minimum 0)
        """
        score = 0
        
        # Time survived scoring
        score += int(stats['time_survived'] * 100)
        
        # Victory bonus
        if won:
            score += 50000
        
        # Event handling scoring
        score += stats['events_resolved'] * 1000
        score -= stats['events_failed'] * 500
        
        # Sector management scoring
        for sector_stats in stats['sectors'].values():
            score += sector_stats['final_level'] * 10  # Reward for keeping levels high
            score -= sector_stats['critical_warnings'] * 100  # Penalty for letting sectors get critical
        
        return max(0, score)  # Don't allow negative scores
    
    def load_leaderboard(self):
        """
        Load the leaderboard from the JSON file.
        
        Returns:
            list: List of leaderboard entries, or empty list if file doesn't exist
        """
        if os.path.exists(self.leaderboard_file):
            try:
                with open(self.leaderboard_file, 'r') as f:
                    return json.load(f)
            except:
                return []  # Return empty list if file is corrupted
        return []  # No file exists yet
    
    def save_leaderboard(self, leaderboard):
        """
        Save the leaderboard to the JSON file.
        
        Args:
            leaderboard: List of leaderboard entries to save
        """
        try:
            with open(self.leaderboard_file, 'w') as f:
                json.dump(leaderboard, f, indent=2)
        except:
            pass  # Silently fail if unable to save
    
    def add_to_leaderboard(self, score, won, stats):
        """
        Add the current game result to the leaderboard.
        Keeps only the top 10 scores.
        
        Args:
            score: Final score achieved
            won: Boolean indicating if player won
            stats: Dictionary of game statistics
            
        Returns:
            list: Updated leaderboard
        """
        leaderboard = self.load_leaderboard()
        
        # Format time survived for display
        minutes = int(stats['time_survived'] // 60)
        seconds = int(stats['time_survived'] % 60)
        
        # Create new leaderboard entry
        entry = {
            'score': score,
            'won': won,
            'time': f"{minutes}m {seconds}s",
            'time_seconds': stats['time_survived'],  # Keep raw value for sorting
            'events_resolved': stats['events_resolved'],
            'events_failed': stats['events_failed'],
            'date': datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        
        # Add entry and sort by score (highest first)
        leaderboard.append(entry)
        leaderboard.sort(key=lambda x: x['score'], reverse=True)
        leaderboard = leaderboard[:10]  # Keep only top 10
        
        # Save updated leaderboard
        self.save_leaderboard(leaderboard)
        return leaderboard
    
    def show_leaderboard(self, parent, current_score, won):
        """
        Display the leaderboard in a scrollable list.
        Highlights the current game's score if it made the top 10.
        
        Args:
            parent: Parent frame to display leaderboard in
            current_score: The score from the game that just ended
            won: Whether the current game was won
        """
        # Title
        tk.Label(parent, text="🏆 Top 10 High Scores", font=('Arial', 16, 'bold'),
                bg='#34495e', fg='#f1c40f').pack(pady=15)
        
        # Create scrollable canvas for leaderboard entries
        canvas = tk.Canvas(parent, bg='#34495e', highlightthickness=0)
        scrollbar = tk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#34495e')
        
        # Configure scrolling
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        scrollbar.pack(side="right", fill="y")
        
        leaderboard = self.load_leaderboard()
        
        # Handle empty leaderboard
        if not leaderboard:
            tk.Label(scrollable_frame, text="No scores yet! Be the first!",
                    font=('Arial', 12), bg='#34495e', fg='#ecf0f1').pack(pady=20)
        else:
            # Create header row with column labels
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
            
            # Display each leaderboard entry
            for i, entry in enumerate(leaderboard, 1):
                # Check if this is the current game's score (and it's at the top)
                is_current = (entry['score'] == current_score and i == 1 and entry == leaderboard[0])
                bg_color = '#27ae60' if is_current else '#34495e'  # Green highlight for new top score
                
                # Create frame for this entry
                entry_frame = tk.Frame(scrollable_frame, bg=bg_color, padx=10, pady=8)
                entry_frame.pack(fill=tk.X, pady=3, padx=10)
                
                # Rank display with medal emojis for top 3
                rank_text = f"🥇 #{i}" if i == 1 else f"🥈 #{i}" if i == 2 else f"🥉 #{i}" if i == 3 else f"#{i}"
                tk.Label(entry_frame, text=rank_text, font=('Arial', 11, 'bold'),
                        bg=bg_color, fg='#f1c40f' if i <= 3 else '#ecf0f1', width=6).grid(row=0, column=0, padx=5)
                
                # Score with comma formatting
                score_text = f"{entry['score']:,}"
                tk.Label(entry_frame, text=score_text, font=('Arial', 10),
                        bg=bg_color, fg='#ecf0f1', width=12).grid(row=0, column=1, padx=5)
                
                # Time with win/loss indicator
                result_icon = "🎉" if entry.get('won', False) else "💀"
                time_text = f"{result_icon} {entry['time']}"
                tk.Label(entry_frame, text=time_text, font=('Arial', 10),
                        bg=bg_color, fg='#ecf0f1', width=10).grid(row=0, column=2, padx=5)
                
                # Events resolved/failed
                events_text = f"✓{entry['events_resolved']} ✗{entry['events_failed']}"
                tk.Label(entry_frame, text=events_text, font=('Arial', 10),
                        bg=bg_color, fg='#ecf0f1', width=10).grid(row=0, column=3, padx=5)
                
                # Date/time of game
                tk.Label(entry_frame, text=entry['date'], font=('Arial', 9),
                        bg=bg_color, fg='#95a5a6', width=15).grid(row=0, column=4, padx=5)
                
                # Mark if this is the new score
                if is_current:
                    tk.Label(entry_frame, text="← NEW!", font=('Arial', 10, 'bold'),
                            bg=bg_color, fg='#f1c40f').grid(row=0, column=5, padx=10)
    
    def show_end_screen(self, won, failed_sector, stats):
        """
        Display the end game screen with statistics and leaderboard.
        Shows detailed performance breakdown in tabbed interface.
        
        Args:
            won: Boolean indicating if player won
            failed_sector: Name of sector that caused game over (None if won)
            stats: Dictionary of complete game statistics
        """
        # Create new popup window
        end_window = tk.Toplevel(self.root)
        end_window.title("Game Over" if not won else "Victory!")
        end_window.geometry("700x650")
        end_window.configure(bg='#2c3e50')
        end_window.grab_set()  # Make this window modal (blocks main window)
        
        # Display victory or game over title
        title_text = "🎉 VICTORY!" if won else "💀 GAME OVER"
        title_color = '#27ae60' if won else '#e74c3c'
        
        title = tk.Label(end_window, text=title_text, font=('Arial', 24, 'bold'),
                        bg='#2c3e50', fg=title_color)
        title.pack(pady=15)
        
        # Display reason for game end
        if not won:
            result_msg = f"⚠️ {failed_sector} ran out of water"
            tk.Label(end_window, text=result_msg, font=('Arial', 14),
                    bg='#2c3e50', fg='#e74c3c').pack(pady=5)
        else:
            result_msg = "You successfully managed the city!"
            tk.Label(end_window, text=result_msg, font=('Arial', 14),
                    bg='#2c3e50', fg='#27ae60').pack(pady=5)
        
        # Create tabbed interface for stats and leaderboard
        notebook = ttk.Notebook(end_window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # ===== STATS TAB =====
        stats_tab = tk.Frame(notebook, bg='#34495e')
        notebook.add(stats_tab, text="📊 Your Stats")
        
        # Create scrollable canvas for stats (in case of many sectors)
        canvas = tk.Canvas(stats_tab, bg='#34495e', highlightthickness=0)
        scrollbar = tk.Scrollbar(stats_tab, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='#34495e')
        
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        scrollbar.pack(side="right", fill="y")
        
        # Format time survived
        minutes = int(stats['time_survived'] // 60)
        seconds = int(stats['time_survived'] % 60)
        
        # Performance summary header
        tk.Label(scrollable_frame, text="⏱️ Performance Summary", font=('Arial', 16, 'bold'),
                bg='#34495e', fg='white').pack(pady=10)
        
        # Calculate and display final score
        score = self.calculate_score(stats, won)
        tk.Label(scrollable_frame, text=f"SCORE: {score:,}", 
                font=('Arial', 14, 'bold'), bg='#34495e', fg='#f1c40f').pack(pady=5)
        
        # Display overall statistics
        tk.Label(scrollable_frame, text=f"Time Survived: {minutes}m {seconds}s", 
                font=('Arial', 12), bg='#34495e', fg='#3498db').pack(pady=5)
        
        tk.Label(scrollable_frame, text=f"Events Resolved: {stats['events_resolved']}", 
                font=('Arial', 12), bg='#34495e', fg='#2ecc71').pack(pady=3)
        
        tk.Label(scrollable_frame, text=f"Events Failed: {stats['events_failed']}", 
                font=('Arial', 12), bg='#34495e', fg='#e74c3c').pack(pady=3)
        
        tk.Label(scrollable_frame, text=f"Total Allocations: {stats['total_allocations']}", 
                font=('Arial', 12), bg='#34495e', fg='#ecf0f1').pack(pady=3)
        
        # Sector statistics header
        tk.Label(scrollable_frame, text="\n📊 Sector Statistics", font=('Arial', 14, 'bold'),
                bg='#34495e', fg='white').pack(pady=10)
        
        # Display detailed stats for each sector
        for sector_name, sector_stats in stats['sectors'].items():
            sector_frame = tk.Frame(scrollable_frame, bg='#2c3e50', padx=10, pady=8)
            sector_frame.pack(fill=tk.X, pady=5, padx=10)
            
            # Highlight failed sector in red
            name_color = '#e74c3c' if sector_name == failed_sector else '#ecf0f1'
            
            # Sector name
            tk.Label(sector_frame, text=f"🏢 {sector_name}", font=('Arial', 11, 'bold'),
                    bg='#2c3e50', fg=name_color).pack(anchor='w')
            
            # Sector statistics (indented for hierarchy)
            tk.Label(sector_frame, text=f"  Final Level: {sector_stats['final_level']}/100",
                    font=('Arial', 10), bg='#2c3e50', fg='#ecf0f1').pack(anchor='w')
            
            tk.Label(sector_frame, text=f"  Total Consumed: {sector_stats['total_consumed']}",
                    font=('Arial', 10), bg='#2c3e50', fg='#ecf0f1').pack(anchor='w')
            
            tk.Label(sector_frame, text=f"  Total Allocated: {sector_stats['total_allocated']}",
                    font=('Arial', 10), bg='#2c3e50', fg='#ecf0f1').pack(anchor='w')
            
            tk.Label(sector_frame, text=f"  Critical Warnings: {sector_stats['critical_warnings']}",
                    font=('Arial', 10), bg='#2c3e50', fg='#f39c12').pack(anchor='w')
        
        # ===== LEADERBOARD TAB =====
        leaderboard_tab = tk.Frame(notebook, bg='#34495e')
        notebook.add(leaderboard_tab, text="🏆 Leaderboard")
        
        # Add current score to leaderboard and display
        self.add_to_leaderboard(score, won, stats)
        self.show_leaderboard(leaderboard_tab, score, won)
        
        # ===== ACTION BUTTONS =====
        btn_frame = tk.Frame(end_window, bg='#2c3e50')
        btn_frame.pack(pady=15)
        
        # Play again button
        tk.Button(btn_frame, text="Play Again", font=('Arial', 12, 'bold'),
                 bg='#27ae60', fg='white', width=15, height=2,
                 command=lambda: self.restart_game(end_window)).pack(side=tk.LEFT, padx=10)
        
        # Quit button
        tk.Button(btn_frame, text="Quit", font=('Arial', 12, 'bold'),
                 bg='#e74c3c', fg='white', width=15, height=2,
                 command=self.root.quit).pack(side=tk.LEFT, padx=10)
    
    def restart_game(self, end_window):
        """
        Restart the game with fresh state.
        Closes the end screen and starts a new game.
        
        Args:
            end_window: The end screen window to close
        """
        end_window.destroy()  # Close end screen
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