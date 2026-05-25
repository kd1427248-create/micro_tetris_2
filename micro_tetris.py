import machine
import time
import random
from machine import Pin, I2C, PWM
import ssd1306
import neopixel

print("LOCKDOWN TETRIS START!")

try:
    # --- 縦持ち用のボタン割り当て ---
    sw_left = Pin(6, Pin.IN, Pin.PULL_UP)    # SW3: 左に移動
    sw_right = Pin(2, Pin.IN, Pin.PULL_UP)   # SW1: 右に移動
    sw_rotate = Pin(3, Pin.IN, Pin.PULL_UP)  # SW2: 回転

    # PWMスピーカー初期化
    speaker = PWM(Pin(21))
    DUTY = 20000  # 音量
    speaker.duty_u16(0)

    # フルカラーLED (ピン10)
    NUM_LEDS = 3
    rgb_pin = Pin(10, Pin.OUT)
    np = neopixel.NeoPixel(rgb_pin, NUM_LEDS)

    # OLEDディスプレイ
    i2c = I2C(0, scl=Pin(9), sda=Pin(8)) 
    oled = ssd1306.SSD1306_I2C(128, 64, i2c)

    # --- テトリスの設定 ---
    BLOCK_SIZE = 5
    FIELD_W = 10
    FIELD_H = 18       
    OFFSET_X = 2
    OFFSET_Y = 2

    # NEXTエリア・SCOREエリアの位置
    NEXT_X = 15
    NEXT_Y = 105
    SCORE_X = 56
    SCORE_Y = 10

    field = [[0] * FIELD_W for _ in range(FIELD_H)]

    SHAPES = [
        [[1,1,1,1]], [[1,1,1],[0,1,0]], [[1,1,1],[1,0,0]],
        [[1,1,1],[0,0,1]], [[1,1],[1,1]], [[1,1,0],[0,1,1]], [[0,1,1],[1,1,0]]
    ]

    # BGM用の音階データ (コロブチカ)
    NOTE_E5 = 659; NOTE_B4 = 494; NOTE_C5 = 523; NOTE_D5 = 587; NOTE_A4 = 440; NOTE_G4 = 392; NOTE_F4 = 349
    bgm_notes = [
        NOTE_E5, NOTE_B4, NOTE_C5, NOTE_D5, NOTE_C5, NOTE_B4, NOTE_A4, NOTE_A4,
        NOTE_C5, NOTE_E5, NOTE_D5, NOTE_C5, NOTE_B4, NOTE_C5, NOTE_D5, NOTE_E5,
        NOTE_C5, NOTE_A4, NOTE_A4, 0,
        NOTE_D5, NOTE_F4, NOTE_A4, NOTE_D5, NOTE_C5, NOTE_B4,
        NOTE_C5, NOTE_E5, NOTE_D5, NOTE_C5, NOTE_B4, NOTE_C5, NOTE_D5, NOTE_E5,
        NOTE_C5, NOTE_A4, NOTE_A4, 0
    ]
    bgm_index = 0
    last_bgm_time = time.ticks_ms()

    # --- 縦持ち用 自作5x5数字フォントデータ ---
    FONT = {
        '0': [[1,1,1],[1,0,1],[1,0,1],[1,0,1],[1,1,1]],
        '1': [[0,1,0],[0,1,0],[0,1,0],[0,1,0],[0,1,0]],
        '2': [[1,1,1],[0,0,1],[1,1,1],[1,0,0],[1,1,1]],
        '3': [[1,1,1],[0,0,1],[1,1,1],[0,0,1],[1,1,1]],
        '4': [[1,0,1],[1,0,1],[1,1,1],[0,0,1],[0,0,1]],
        '5': [[1,1,1],[1,0,0],[1,1,1],[0,0,1],[1,1,1]],
        '6': [[1,1,1],[1,0,0],[1,1,1],[1,0,1],[1,1,1]],
        '7': [[1,1,1],[0,0,1],[0,1,0],[0,1,0],[0,1,0]],
        '8': [[1,1,1],[1,0,1],[1,1,1],[1,0,1],[1,1,1]],
        '9': [[1,1,1],[1,0,1],[1,1,1],[0,0,1],[1,1,1]]
    }

    # --- サウンド関数 ---
    def play_tone(freq, duration_ms):
        if freq == 0: speaker.duty_u16(0); time.sleep_ms(duration_ms); return
        speaker.freq(freq); speaker.duty_u16(DUTY); time.sleep_ms(duration_ms); speaker.duty_u16(0)

    def se_clear():
        for f in range(800, 2000, 200):
            speaker.freq(f); speaker.duty_u16(DUTY); time.sleep_ms(20)
        speaker.duty_u16(0)

    def se_harddrop():
        for f in range(300, 100, -30):
            speaker.freq(f); speaker.duty_u16(DUTY); time.sleep_ms(15)
        speaker.duty_u16(0)

    def se_gameover():
        play_tone(400, 150); play_tone(350, 150); play_tone(250, 400)

    # --- 縦画面描画用の関数群 ---
    def draw_pixel_ver(x, y, color):
        if 0 <= x < 64 and 0 <= y < 128: oled.pixel(127 - y, x, color)

    def fill_rect_ver(x, y, w, h, color):
        for i in range(w):
            for j in range(h): draw_pixel_ver(x + i, y + j, color)

    def rect_ver(x, y, w, h, color):
        for i in range(w): draw_pixel_ver(x + i, y, color); draw_pixel_ver(x + i, y + h - 1, color)
        for j in range(h): draw_pixel_ver(x, y + j, color); draw_pixel_ver(x + w - 1, y + j, color)

    def draw_number_ver(start_x, start_y, num_str):
        current_y = start_y
        for char in num_str:
            if char in FONT:
                bitmap = FONT[char]
                for r in range(5):
                    for c in range(3):
                        if bitmap[r][c]: draw_pixel_ver(start_x + c, current_y + r, 1)
                current_y += 7 

    def draw_next_text():
        # "N"
        fill_rect_ver(4, 96, 1, 5, 1); draw_pixel_ver(5, 97, 1); draw_pixel_ver(6, 99, 1); fill_rect_ver(7, 96, 1, 5, 1)
        # "E"
        fill_rect_ver(10, 96, 3, 1, 1); fill_rect_ver(10, 98, 2, 1, 1); fill_rect_ver(10, 100, 3, 1, 1); fill_rect_ver(10, 96, 1, 5, 1)
        # "X"
        draw_pixel_ver(15, 96, 1); draw_pixel_ver(17, 96, 1); draw_pixel_ver(16, 98, 1); draw_pixel_ver(15, 100, 1); draw_pixel_ver(17, 100, 1)
        # "T"
        fill_rect_ver(20, 96, 3, 1, 1); fill_rect_ver(21, 96, 1, 5, 1)

    def check_collision(shape, offset_x, offset_y):
        for r, row in enumerate(shape):
            for c, val in enumerate(row):
                if val:
                    new_x = offset_x + c; new_y = offset_y + r
                    if new_x < 0 or new_x >= FIELD_W or new_y >= FIELD_H: return True
                    if new_y >= 0 and field[new_y][new_x]: return True
        return False

    def rotate_shape(shape): return [list(x) for x in zip(*shape[::-1])]

    def draw_game(cur_shape, cur_x, cur_y, next_shape, score):
        oled.fill(0)
        rect_ver(OFFSET_X - 1, OFFSET_Y - 1, FIELD_W * BLOCK_SIZE + 2, FIELD_H * BLOCK_SIZE + 2, 1)
        
        # 固定ブロック
        for r in range(FIELD_H):
            for c in range(FIELD_W):
                if field[r][c]: fill_rect_ver(OFFSET_X + c * BLOCK_SIZE, OFFSET_Y + r * BLOCK_SIZE, BLOCK_SIZE - 1, BLOCK_SIZE - 1, 1)
                    
        # 落下中ブロック
        for r, row in enumerate(cur_shape):
            for c, val in enumerate(row):
                if val: fill_rect_ver(OFFSET_X + (cur_x + c) * BLOCK_SIZE, OFFSET_Y + (cur_y + r) * BLOCK_SIZE, BLOCK_SIZE - 1, BLOCK_SIZE - 1, 1)
        
        # NEXT表示
        draw_next_text()
        for r, row in enumerate(next_shape):
            for c, val in enumerate(row):
                if val: fill_rect_ver(NEXT_X + c * BLOCK_SIZE, NEXT_Y + r * BLOCK_SIZE, BLOCK_SIZE - 1, BLOCK_SIZE - 1, 1)

        # スコア数字表示
        score_str = str(score)
        draw_number_ver(SCORE_X, SCORE_Y, score_str)
            
        # LED演出
        for i in range(NUM_LEDS): np[i] = (0, 15, 5) if state != "GAME_OVER" else (20, 0, 0)
        np.write()
            
        oled.show()

    # --- ゲームメイン処理 ---
    score = 0
    game_over = False
    state = "PLAY"
    last_drop = time.ticks_ms()
    drop_interval = 500 

    # 【追加】固着猶予用の変数たち
    is_grounded = False
    lock_start_time = 0
    LOCK_DELAY_MS = 500  # 猶予時間：0.5秒（ここを増やすともっとぬるくなります）
    manipulation_count = 0
    MAX_MANIPULATIONS = 15 # リセット回数の上限

    current_shape = random.choice(SHAPES)
    next_shape = random.choice(SHAPES)
    current_x = FIELD_W // 2 - len(current_shape[0]) // 2
    current_y = 0

    while not game_over:
        # 1. バックグラウンドBGM
        if time.ticks_diff(time.ticks_ms(), last_bgm_time) > 240:
            note = bgm_notes[bgm_index]
            if sw_left.value() == 1 and sw_right.value() == 1 and sw_rotate.value() == 1:
                if note > 0:
                    speaker.freq(note); speaker.duty_u16(DUTY); time.sleep_ms(70); speaker.duty_u16(0)
            bgm_index = (bgm_index + 1) % len(bgm_notes)
            last_bgm_time = time.ticks_ms()

        # 下が詰まっている（接地している状態）かを事前にチェック
        currently_on_ground = check_collision(current_shape, current_x, current_y + 1)

        # 2. ボタン入力
        # 左右同時押しでハードドロップ（猶予なしで即固定）
        if sw_left.value() == 0 and sw_right.value() == 0:
            while not check_collision(current_shape, current_x, current_y + 1): current_y += 1
            se_harddrop()
            # 即座に固定プロセスに進むようにタイマーをリセット
            is_grounded = True
            lock_start_time = time.ticks_ms() - LOCK_DELAY_MS - 1
            time.sleep(0.2)
        else:
            action_taken = False
            
            if sw_left.value() == 0:
                if not check_collision(current_shape, current_x - 1, current_y): 
                    current_x -= 1; play_tone(880, 25); action_taken = True
                time.sleep(0.08)
                
            if sw_right.value() == 0:
                if not check_collision(current_shape, current_x + 1, current_y): 
                    current_x += 1; play_tone(880, 25); action_taken = True
                time.sleep(0.08)
                
            if sw_rotate.value() == 0:
                rotated = rotate_shape(current_shape)
                if not check_collision(rotated, current_x, current_y): 
                    current_shape = rotated; play_tone(1200, 35); action_taken = True
                time.sleep(0.12)

            # 接地中に動かしたら、猶予タイマーを最初からリセットする（本家テトリス風システム）
            if currently_on_ground and action_taken and manipulation_count < MAX_MANIPULATIONS:
                lock_start_time = time.ticks_ms() # タイマーを今に引き延ばす
                manipulation_count += 1

        # 3. 落下・固着猶予システムロジック
        if currently_on_ground:
            if not is_grounded:
                # 初めて地面に着いた瞬間：猶予タイマースタート
                is_grounded = True
                lock_start_time = time.ticks_ms()
            
            # 猶予時間が切れたら、ついにブロックを固定する
            if time.ticks_diff(time.ticks_ms(), lock_start_time) > LOCK_DELAY_MS:
                # フィールドへの固定処理
                for r, row in enumerate(current_shape):
                    for c, val in enumerate(row):
                        if val and current_y + r >= 0: field[current_y + r][current_x + c] = 1
                
                # ライン消去
                new_field = [row for row in field if not all(row)]
                lines_cleared = FIELD_H - len(new_field)
                if lines_cleared > 0:
                    se_clear()
                    score += lines_cleared * 100
                    field = [[0] * FIELD_W for _ in range(lines_cleared)] + new_field
                else:
                    # 通常接地音
                    if not (sw_left.value() == 0 and sw_right.value() == 0): play_tone(440, 20)
                
                # 次のブロックへ交代
                current_shape = next_shape
                next_shape = random.choice(SHAPES)
                current_x = FIELD_W // 2 - len(current_shape[0]) // 2; current_y = 0
                
                # 初期化
                is_grounded = False
                manipulation_count = 0
                
                if check_collision(current_shape, current_x, current_y): game_over = True; state = "GAME_OVER"
                last_drop = time.ticks_ms()
        else:
            # 空中にいるときは猶予状態を解除
            is_grounded = False
            # 通常の自動落下処理
            if time.ticks_diff(time.ticks_ms(), last_drop) > drop_interval:
                current_y += 1
                last_drop = time.ticks_ms()

        # 4. 描画
        draw_game(current_shape, current_x, current_y, next_shape, score)
        time.sleep(0.01)

    # --- ゲームオーバー ---
    print("GAME OVER. FINAL SCORE:", score)
    se_gameover()
    for i in range(NUM_LEDS): np[i] = (40, 0, 0)
    np.write()
    oled.fill(0)
    for y in range(0, 128, 4):
        for x in range(0, 64, 4): draw_pixel_ver(x, y, 1)
        oled.show(); time.sleep(0.01)

except Exception as e:
    speaker.duty_u16(0)
    print("エラーが発生しました:", e)