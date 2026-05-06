import pygame
import time
import random
import asyncio
import threading
from dotenv import load_dotenv
import struct
import math
from omi import listen_to_omi

load_dotenv()

# Pygame setup
pygame.init() 
clock = pygame.time.Clock()

# Colors
BLACK = (0,0,0)
RED = (255,0,0)
WHITE = (255,255,255)
GREEN = (0,255,0)
YELLOW = (255,255,0)
CYAN = (0,255,255)
PURPLE = (255,0,255)
ORANGE = (255,165,0)

# Window - 2x scale
wn_width = 1000
wn_height = 800
wn = pygame.display.set_mode((wn_width,wn_height))
pygame.display.set_caption('Voice-Controlled Space Racer')

# Images - scale 2x
bg_original = pygame.image.load('images/starfield.png')
bg = pygame.transform.scale(bg_original, (wn_width, wn_height))

carimg_original = pygame.image.load('images/rocket.png')
car_width = carimg_original.get_width() * 2
car_height = carimg_original.get_height() * 2
carimg = pygame.transform.scale(carimg_original, (car_width, car_height))

# Omi device settings
DEVICE_ID = "046AC44C-4ED2-67B2-586E-71E710920E2C"
OMI_CHAR_UUID = "19B10001-E8F2-537E-4F6C-D104768A1214"

# Voice control settings
AMPLITUDE_THRESHOLD = 10.0
current_amplitude = 0.0
last_switch_time = 0
SWITCH_COOLDOWN = 0.5

# Lane positions
LEFT_LANE_BLOCK = 183 * 2
RIGHT_LANE_BLOCK = 284 * 2
LEFT_LANE_SHIP = 190 * 2
RIGHT_LANE_SHIP = 280 * 2

# Game state
high_score = 0
combo_count = 0
last_dodge_time = 0

def calculate_rms_amplitude(pcm_data):
    """Calculate RMS amplitude from 16-bit PCM data"""
    if len(pcm_data) < 2:
        return 0
    
    num_samples = len(pcm_data) // 2
    samples = struct.unpack(f'<{num_samples}h', pcm_data)
    
    sum_squares = sum(s * s for s in samples)
    rms = math.sqrt(sum_squares / num_samples)
    
    normalized = (rms / 32768.0) * 100
    return normalized

class Particle:
    """Particle effect for lane switching"""
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.vx = random.uniform(-5, 5)
        self.vy = random.uniform(-5, 5)
        self.life = 30
        self.color = random.choice([CYAN, WHITE, YELLOW])
        
    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.life -= 1
        
    def draw(self, wn):
        if self.life > 0:
            alpha = int(255 * (self.life / 30))
            size = max(1, int(4 * (self.life / 30)))
            pygame.draw.circle(wn, self.color, (int(self.x), int(self.y)), size)

class Block:
    def __init__(self, lane, block_type='normal'):
        self.lane = lane
        self.block_type = block_type
        
        if block_type == 'big':
            self.width = 80 * 2
            self.height = 30 * 2
            self.color = ORANGE
            self.speedy = 8
        elif block_type == 'fast':
            self.width = 40 * 2
            self.height = 15 * 2
            self.color = YELLOW
            self.speedy = 15
        else:  # normal
            self.width = 50 * 2
            self.height = 20 * 2
            self.color = RED
            self.speedy = 10
        
        self.x = LEFT_LANE_BLOCK if lane == 'left' else RIGHT_LANE_BLOCK
        self.y = -200
        self.dodged = False
        
    def update(self):
        self.y += self.speedy
        
    def draw(self, wn):
        # Draw with glow effect
        pygame.draw.rect(wn, self.color, [self.x, self.y, self.width, self.height])
        pygame.draw.rect(wn, WHITE, [self.x, self.y, self.width, self.height], 3)

class Player:
    def __init__(self):
        self.image = carimg
        self.width = self.image.get_width()
        self.height = self.image.get_height()
        
        self.rect = self.image.get_rect()
        self.lane = 'right'
        self.rect.x = RIGHT_LANE_SHIP
        self.rect.y = wn_height - 200
        
        # Animation
        self.target_x = self.rect.x
        self.switching = False
        
    def switch_lane(self):
        """Switch to the opposite lane with animation"""
        global last_switch_time, particles
        current_time = time.time()
        
        if current_time - last_switch_time > SWITCH_COOLDOWN:
            if self.lane == 'left':
                self.lane = 'right'
                self.target_x = RIGHT_LANE_SHIP
            else:
                self.lane = 'left'
                self.target_x = LEFT_LANE_SHIP
            
            last_switch_time = current_time
            self.switching = True
            
            # Create particles
            for _ in range(10):
                particles.append(Particle(self.rect.centerx, self.rect.centery))
            
            print(f"🚀 Switched to {self.lane.upper()} lane!")
    
    def update(self):
        # Smooth lane switching animation
        if self.switching:
            diff = self.target_x - self.rect.x
            if abs(diff) > 5:
                self.rect.x += diff * 0.3
            else:
                self.rect.x = self.target_x
                self.switching = False

def score_board(blocks_manager):
    font_large = pygame.font.Font(None, 60)
    font_small = pygame.font.Font(None, 40)
    
    # Score
    score_text = font_large.render(f'Score: {blocks_manager.score}', True, WHITE)
    wn.blit(score_text, (20, 20))
    
    # High score
    high_text = font_small.render(f'High: {high_score}', True, YELLOW)
    wn.blit(high_text, (20, 85))
    
    # Combo
    if combo_count > 1:
        combo_text = font_large.render(f'COMBO x{combo_count}!', True, CYAN)
        wn.blit(combo_text, (wn_width//2 - 100, 100))
    
    # Difficulty level
    level_text = font_small.render(f'Level: {blocks_manager.get_level()}', True, GREEN)
    wn.blit(level_text, (20, 130))
    
    # Amplitude meter
    bar_width = 250
    bar_height = 25
    bar_x = wn_width - bar_width - 20
    bar_y = 20
    
    # Background
    pygame.draw.rect(wn, BLACK, [bar_x-5, bar_y-5, bar_width+10, bar_height+10])
    pygame.draw.rect(wn, WHITE, [bar_x, bar_y, bar_width, bar_height], 3)
    
    # Fill
    filled_width = int((current_amplitude / 100) * bar_width)
    if current_amplitude > AMPLITUDE_THRESHOLD:
        color = GREEN
    else:
        color = RED
    pygame.draw.rect(wn, color, [bar_x, bar_y, filled_width, bar_height])
    
    # Threshold line
    threshold_x = bar_x + int((AMPLITUDE_THRESHOLD / 100) * bar_width)
    pygame.draw.line(wn, YELLOW, (threshold_x, bar_y), (threshold_x, bar_y + bar_height), 3)
    
    # Label
    vol_text = font_small.render('VOICE', True, WHITE)
    wn.blit(vol_text, (bar_x, bar_y + bar_height + 5))

class BlocksManager:
    def __init__(self):
        self.blocks = []
        self.score = 0
        self.spawn_timer = 0
        self.spawn_interval = 100  # Frames between spawns
        
    def get_level(self):
        return (self.score // 10) + 1
    
    def get_spawn_interval(self):
        # Decrease spawn interval as score increases (faster spawning)
        return max(40, 100 - (self.score // 5) * 5)
    
    def update(self, player):
        global combo_count, last_dodge_time
        
        self.spawn_timer += 1
        current_interval = self.get_spawn_interval()
        
        # Spawn new blocks
        if self.spawn_timer >= current_interval:
            self.spawn_timer = 0
            
            # Random block type based on score
            if self.score > 20 and random.random() < 0.2:
                block_type = 'fast'
            elif self.score > 10 and random.random() < 0.15:
                block_type = 'big'
            else:
                block_type = 'normal'
            
            lane = random.choice(['left', 'right'])
            self.blocks.append(Block(lane, block_type))
        
        # Update blocks
        for block in self.blocks[:]:
            block.update()
            
            # Check if passed player (dodged)
            if not block.dodged and block.y > player.rect.y + player.height:
                block.dodged = True
                self.score += 1
                
                # Combo system
                current_time = time.time()
                if current_time - last_dodge_time < 2:  # Within 2 seconds
                    combo_count += 1
                else:
                    combo_count = 1
                last_dodge_time = current_time
                
                print(f"✅ Dodged! Score: {self.score} (Combo x{combo_count})")
            
            # Remove off-screen blocks
            if block.y > wn_height + 100:
                self.blocks.remove(block)
    
    def draw(self, wn):
        for block in self.blocks:
            block.draw(wn)
    
    def check_collision(self, player):
        for block in self.blocks:
            if player.lane == block.lane:
                # Simple collision detection
                if (block.y < player.rect.y + player.height and 
                    block.y + block.height > player.rect.y):
                    return True
        return False

def crash(blocks_manager):
    global high_score, combo_count
    
    # Update high score
    if blocks_manager.score > high_score:
        high_score = blocks_manager.score
        new_record = True
    else:
        new_record = False
    
    # Game over screen
    wn.blit(bg, (0, 0))
    
    font_huge = pygame.font.Font(None, 160)
    font_large = pygame.font.Font(None, 80)
    font_med = pygame.font.Font(None, 50)
    
    # Game over text
    game_over = font_huge.render('GAME OVER!', True, RED)
    wn.blit(game_over, (wn_width//2 - game_over.get_width()//2, 150))
    
    # Score
    score_text = font_large.render(f'Final Score: {blocks_manager.score}', True, WHITE)
    wn.blit(score_text, (wn_width//2 - score_text.get_width()//2, 320))
    
    # High score
    if new_record:
        record_text = font_med.render('NEW HIGH SCORE!', True, YELLOW)
        wn.blit(record_text, (wn_width//2 - record_text.get_width()//2, 400))
    else:
        high_text = font_med.render(f'High Score: {high_score}', True, YELLOW)
        wn.blit(high_text, (wn_width//2 - high_text.get_width()//2, 400))
    
    pygame.display.update()
    
    # Reset combo
    combo_count = 0
    
    # Auto-restart countdown
    for i in range(3, 0, -1):
        # Show countdown
        countdown_text = font_huge.render(str(i), True, CYAN)
        
        # Redraw screen with countdown
        wn.blit(bg, (0, 0))
        game_over = font_huge.render('GAME OVER!', True, RED)
        wn.blit(game_over, (wn_width//2 - game_over.get_width()//2, 150))
        wn.blit(score_text, (wn_width//2 - score_text.get_width()//2, 320))
        
        if new_record:
            wn.blit(record_text, (wn_width//2 - record_text.get_width()//2, 400))
        else:
            wn.blit(high_text, (wn_width//2 - high_text.get_width()//2, 400))
        
        restart_text = font_med.render(f'Restarting in...', True, WHITE)
        wn.blit(restart_text, (wn_width//2 - restart_text.get_width()//2, 550))
        wn.blit(countdown_text, (wn_width//2 - countdown_text.get_width()//2, 620))
        
        pygame.display.update()
        
        # Check for quit during countdown
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                quit()
        
        time.sleep(1)
    
    game_loop()

def start_omi_listener():
    """Run Omi audio monitoring in background thread"""
    global current_amplitude
    
    def handle_audio(sender, data):
        global current_amplitude
        if isinstance(data, bytearray):
            data = bytes(data)
        
        pcm_data = data[1:]
        current_amplitude = calculate_rms_amplitude(pcm_data)
    
    async def listen():
        await listen_to_omi(DEVICE_ID, OMI_CHAR_UUID, handle_audio)
    
    def run_async():
        asyncio.run(listen())
    
    thread = threading.Thread(target=run_async, daemon=True)
    thread.start()

# Global particles list
particles = []

def game_loop():
    global current_amplitude, particles
    
    player = Player()
    blocks_manager = BlocksManager()
    particles = []
    
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                pygame.quit()
                quit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    player.switch_lane()
        
        # Voice control
        if current_amplitude > AMPLITUDE_THRESHOLD:
            player.switch_lane()
        
        # Update
        player.update()
        blocks_manager.update(player)
        
        # Update particles
        for particle in particles[:]:
            particle.update()
            if particle.life <= 0:
                particles.remove(particle)
        
        # Draw
        wn.blit(bg, (0, 0))
        
        # Draw particles
        for particle in particles:
            particle.draw(wn)
        
        # Draw game objects
        blocks_manager.draw(wn)
        wn.blit(player.image, (player.rect.x, player.rect.y))
        
        # Collision
        if blocks_manager.check_collision(player):
            crash(blocks_manager)
        
        # UI
        score_board(blocks_manager)
        
        pygame.display.update()
        clock.tick(60)

# Main
if __name__ == "__main__":
    print("🎮 Voice-Controlled Space Racer - Enhanced Edition")
    print("🎙️  Shout to switch lanes!")
    print(f"Amplitude threshold: {AMPLITUDE_THRESHOLD}%")
    print("Features: Progressive difficulty, combos, multiple block types!")
    print()
    
    start_omi_listener()
    time.sleep(2)
    
    game_loop()
    pygame.quit()
    quit()