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

# Window - 2x scale
wn_width = 1000
wn_height = 800
wn = pygame.display.set_mode((wn_width,wn_height))
pygame.display.set_caption('Voice-Controlled Race Car')

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

# Lane positions - 2x scale
LEFT_LANE_BLOCK = 183 * 2
RIGHT_LANE_BLOCK = 284 * 2
LEFT_LANE_SHIP = 190 * 2
RIGHT_LANE_SHIP = 280 * 2

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

class Block:
    def __init__(self, lane):
        self.width = 50 * 2  # 2x scale
        self.height = 20 * 2  # 2x scale
        self.lane = lane
        self.x = LEFT_LANE_BLOCK if lane == 'left' else RIGHT_LANE_BLOCK
        self.y = -200
        self.speedy = 5 * 2  # 2x scale
        self.dodged = 0
        
    def update(self):
        self.y = self.y + self.speedy
        if self.y > wn_height:
            self.y = -200
            self.lane = random.choice(['left', 'right'])
            self.x = LEFT_LANE_BLOCK if self.lane == 'left' else RIGHT_LANE_BLOCK
            self.dodged += 1

    def draw(self, wn):
        pygame.draw.rect(wn, RED, [self.x, self.y, self.width, self.height])
                  
class Player:
    def __init__(self):
        self.image = carimg
        self.width = self.image.get_width()
        self.height = self.image.get_height()
        
        self.rect = self.image.get_rect()
        self.lane = 'right'
        self.rect.x = RIGHT_LANE_SHIP
        self.rect.y = wn_height - 200
        
    def switch_lane(self):
        """Switch to the opposite lane"""
        global last_switch_time
        current_time = time.time()
        
        if current_time - last_switch_time > SWITCH_COOLDOWN:
            if self.lane == 'left':
                self.lane = 'right'
                self.rect.x = RIGHT_LANE_SHIP
            else:
                self.lane = 'left'
                self.rect.x = LEFT_LANE_SHIP
            last_switch_time = current_time
            print(f"🚀 Switched to {self.lane.upper()} lane!")

def score_board(dodged):
    font = pygame.font.Font(None, 50)  # 2x font size
    text = font.render(f'Dodged: {dodged}', True, WHITE)
    wn.blit(text, (20, 20))
    
    # Show amplitude meter
    amp_text = font.render(f'Volume: {current_amplitude:.1f}%', True, WHITE)
    wn.blit(amp_text, (20, 80))
    
    # Visual amplitude bar - 2x scale
    bar_width = 300
    bar_height = 30
    bar_x = 20
    bar_y = 140
    pygame.draw.rect(wn, WHITE, [bar_x, bar_y, bar_width, bar_height], 4)
    filled_width = int((current_amplitude / 100) * bar_width)
    pygame.draw.rect(wn, GREEN, [bar_x, bar_y, filled_width, bar_height])
    
    # Threshold line
    threshold_x = bar_x + int((AMPLITUDE_THRESHOLD / 100) * bar_width)
    pygame.draw.line(wn, RED, (threshold_x, bar_y), (threshold_x, bar_y + bar_height), 4)

def crash():
    font = pygame.font.Font(None, 160)  # 2x font size
    text = font.render('GAME OVER!', True, WHITE)
    text_width = text.get_width()
    text_height = text.get_height()
    x = int(wn_width/2 - text_width/2)
    y = int(wn_height/2 - text_height/2)
    wn.blit(text, (x, y))
    pygame.display.update()
    time.sleep(2)
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

def game_loop():
    global current_amplitude
    
    player = Player()
    block = Block(random.choice(['left', 'right']))
    
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
        block.update()
        
        # Draw
        wn.blit(bg, (0, 0))
        wn.blit(player.image, (player.rect.x, player.rect.y))
        block.draw(wn)
        
        # Collision detection
        if player.lane == block.lane:
            if abs(player.rect.y - block.y) < player.height:
                crash()
        
        score_board(block.dodged)
        
        pygame.display.update()
        clock.tick(60)

# Main
if __name__ == "__main__":
    print("🎮 Voice-Controlled Racing Game")
    print("🎙️  Shout to switch lanes!")
    print(f"Amplitude threshold: {AMPLITUDE_THRESHOLD}%\n")
    
    start_omi_listener()
    time.sleep(2)
    
    game_loop()
    pygame.quit()
    quit()