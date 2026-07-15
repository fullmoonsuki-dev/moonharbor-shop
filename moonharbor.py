#!/usr/bin/env python3
"""Moonharbor Shop V0.

A small text game for AI players and human spectators.
Public integration surface:

    import moonharbor
    print(moonharbor.cmd("new_game name=小燈 seed=moonharbor-demo player=little_lamp"))
    print(moonharbor.cmd("open_shop tea"))
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


SAVE_VERSION = 1
DEFAULT_PLAYER_ID = "default"
BASE_DIR = Path(__file__).resolve().parent
NO_SAVE_MESSAGE = (
    "這個存檔目錄還沒有月港小店存檔。\n"
    "請先用 `new_game name=店主名 seed=種子 player=玩家ID` 開店；"
    "本次沒有建立或覆寫任何存檔。"
)

SEASONS = ("spring", "summer", "autumn", "winter")
SEASON_NAMES = {
    "spring": "春",
    "summer": "夏",
    "autumn": "秋",
    "winter": "冬",
}
SEASON_WEATHERS = {
    "spring": (
        ("clear", "晴", 35),
        ("drizzle", "細雨", 35),
        ("windy", "有風", 15),
        ("moonfog", "月霧", 10),
        ("starlit", "星光很亮", 5),
    ),
    "summer": (
        ("clear", "晴", 35),
        ("sunny", "晴熱", 30),
        ("windy", "有風", 12),
        ("typhoon", "颱風", 8),
        ("moonfog", "月霧", 8),
        ("starlit", "星光很亮", 7),
    ),
    "autumn": (
        ("autumn_clear", "秋晴", 38),
        ("harvest_breeze", "涼風", 27),
        ("drizzle", "細雨", 10),
        ("morning_mist", "晨霧", 15),
        ("starlit", "星光很亮", 10),
    ),
    "winter": (
        ("winter_clear", "冬晴", 32),
        ("snow", "下雪", 20),
        ("cold_snap", "寒潮", 20),
        ("windy", "有風", 12),
        ("moonfog", "月霧", 10),
        ("starlit", "星光很亮", 6),
    ),
}
COAST_CLOSED_WEATHERS = {"typhoon", "snow"}

LOCATION_ALIASES = {
    "beach": "beach",
    "海邊": "beach",
    "海边": "beach",
    "月潮海岸": "beach",
    "forest": "forest",
    "森林": "forest",
    "鈴葉森林": "forest",
    "铃叶森林": "forest",
    "cave": "cave",
    "洞窟": "cave",
    "星砂洞窟": "cave",
    "lighthouse": "lighthouse",
    "燈塔": "lighthouse",
    "灯塔": "lighthouse",
    "舊燈塔": "lighthouse",
    "旧灯塔": "lighthouse",
}

LOCATIONS = {
    "beach": {
        "name": "月潮海岸",
        "desc": "浪聲很輕，潮線旁有貝殼和細亮的沙。",
        "items": (
            ("sea_salt", 28),
            ("moon_shell", 26),
            ("tide_glass", 18),
            ("small_pearl", 8),
            ("blue_conch", 4),
        ),
    },
    "forest": {
        "name": "鈴葉森林",
        "desc": "樹葉被風吹過時會發出很輕的鈴聲。",
        "items": (
            ("sweet_berry", 30),
            ("bell_leaf", 24),
            ("warm_herb", 24),
            ("firefly_seed", 8),
            ("silver_acorn", 4),
        ),
    },
    "cave": {
        "name": "星砂洞窟",
        "desc": "洞壁有細碎星砂，腳步聲會慢半拍回來。",
        "items": (
            ("crystal_shard", 28),
            ("moon_ore", 24),
            ("echo_geode", 10),
            ("star_core", 4),
        ),
    },
    "lighthouse": {
        "name": "舊燈塔",
        "desc": "燈塔的玻璃很舊，但月光照上去仍然漂亮。",
        "items": (
            ("brass_key", 22),
            ("faded_postcard", 20),
            ("lens_fragment", 16),
            ("old_compass", 8),
            ("keeper_button", 5),
        ),
    },
}

ITEMS = {
    "sea_salt": ("月潮海鹽", "material", "common"),
    "moon_shell": ("月白貝殼", "material", "common"),
    "tide_glass": ("潮汐玻璃", "material", "uncommon"),
    "small_pearl": ("小珍珠", "material", "rare"),
    "blue_conch": ("藍音海螺", "material", "epic"),
    "sweet_berry": ("甜莓", "material", "common"),
    "bell_leaf": ("鈴葉", "material", "common"),
    "warm_herb": ("暖香草", "material", "common"),
    "firefly_seed": ("螢火種子", "material", "rare"),
    "silver_acorn": ("銀橡果", "material", "epic"),
    "crystal_shard": ("水晶碎片", "material", "common"),
    "moon_ore": ("月紋礦", "material", "uncommon"),
    "echo_geode": ("回聲晶洞", "material", "rare"),
    "star_core": ("星核小石", "material", "epic"),
    "brass_key": ("黃銅小鑰匙", "keepsake", "uncommon"),
    "faded_postcard": ("褪色明信片", "keepsake", "common"),
    "lens_fragment": ("燈塔鏡片碎片", "keepsake", "rare"),
    "old_compass": ("舊羅盤", "keepsake", "rare"),
    "keeper_button": ("守燈人鈕扣", "keepsake", "epic"),
}

FISH = (
    ("silver_minfin", "銀線小魚", "fish", "common", 30),
    ("moon_sardine", "月斑沙丁魚", "fish", "common", 26),
    ("blue_tide_bass", "藍潮鱸", "fish", "uncommon", 16),
    ("pearl_bream", "珍珠鯛", "fish", "rare", 8),
    ("star_tail_ray", "星尾魟", "fish", "epic", 3),
    ("harbor_lantern_fish", "月港燈魚", "fish", "legendary", 1),
)

GACHA = (
    ("shell_wind_chime", "貝殼風鈴", "decor", "common", 28),
    ("small_table_lamp", "小桌燈", "decor", "common", 24),
    ("window_seat_cushion", "窗邊坐墊", "decor", "common", 20),
    ("sunny_market_basket", "晴天菜籃", "souvenir", "common", 18),
    ("moon_cufflinks", "月亮袖扣", "wear", "common", 18),
    ("little_chef_hat", "小廚師帽", "wear", "common", 18),
    ("blue_apron", "客用藍邊圍裙", "wear", "uncommon", 16),
    ("moon_mug", "月亮馬克杯", "decor", "uncommon", 15),
    ("counter_note", "櫃檯便條", "keepsake", "uncommon", 14),
    ("matching_cups", "同款杯子", "decor", "uncommon", 13),
    ("star_window_sticker", "星星窗貼", "decor", "uncommon", 12),
    ("shared_dessert_fork", "分給你的甜點叉", "souvenir", "uncommon", 12),
    ("easter_egg_basket", "復活節彩蛋籃", "souvenir", "uncommon", 12),
    ("summer_sparklers", "夏夜手持煙火", "souvenir", "uncommon", 12),
    ("pumpkin_lantern", "南瓜提燈", "souvenir", "uncommon", 12),
    ("christmas_gift_sack", "聖誕禮物袋", "souvenir", "uncommon", 12),
    ("detective_short_cape", "偵探短披風", "wear", "uncommon", 14),
    ("masquerade_mask", "假面舞會面具", "wear", "uncommon", 12),
    ("fox_tail", "狐狸尾巴", "wear", "uncommon", 10),
    ("warm_scarf", "暖色圍巾", "wear", "rare", 8),
    ("mended_little_pot", "修好的小鍋", "decor", "rare", 8),
    ("tiny_lighthouse", "迷你燈塔模型", "decor", "rare", 7),
    ("closing_bell", "打烊鈴", "decor", "rare", 7),
    ("second_little_lamp", "第二盞小燈", "decor", "rare", 6),
    ("small_ledger", "小帳本", "keepsake", "rare", 6),
    ("moonlight_cloak", "月光斗篷", "wear", "rare", 7),
    ("silver_shop_bell", "銀色店鈴", "decor", "epic", 3),
    ("unsigned_charm", "沒有署名的護身符", "keepsake", "epic", 3),
    ("mooncat_coupon", "月港摸頭券", "souvenir", "epic", 2),
    ("magician_set", "魔術師套裝", "wear", "epic", 3),
    ("aurora_shop_sign", "極光招牌", "decor", "legendary", 1),
    ("starlit_formalwear", "星夜禮服", "wear", "legendary", 1),
)

GACHA_DETAILS = {
    "shell_wind_chime": "小小的風鈴帶著海邊氣味，掛起來時，店裡像多了一段不急著結束的午後。",
    "small_table_lamp": "一盞放在桌角的小燈，光不大，卻足夠照亮一杯熱飲和一小段安靜時間。",
    "blue_apron": "這不是店主的基本圍裙，而是留給願意走進櫃檯、臨時幫一把的人。",
    "window_seat_cushion": "軟墊剛好放在窗邊，適合看雨、看海，也適合等一個慢慢回來的人。",
    "sunny_market_basket": "藤編菜籃裡鋪著乾淨布巾，像是把晴天和一點回家的心情一起提了回來。",
    "moon_cufflinks": "一對銀色袖扣，月牙很小，只有轉到光下才看得清。它不張揚，卻會在伸手、翻頁和端起杯子時反覆被看見。",
    "little_chef_hat": "一頂輕巧的小廚師帽，比正式制服柔軟一些。戴好以後，很適合替今天剛出爐的小點認真驕傲一下。",
    "moon_mug": "杯身有一圈很淡的月紋，握在手裡時，連普通熱飲都像被夜色好好照顧過。",
    "counter_note": "便條貼在櫃檯內側，上面寫著：今天也辛苦了，忙完以後要給自己留一點舒服的時間。",
    "matching_cups": "兩只杯子的月紋剛好能對上，放在一起時，比單獨看更安靜。",
    "star_window_sticker": "幾枚小星星貼在窗角，白天不太起眼，夜裡卻讓人知道店裡還留著光。",
    "shared_dessert_fork": "一支小甜點叉，柄端有一枚月牙。它很適合把最後一口留給正在陪你的人。",
    "easter_egg_basket": "藤編小籃裡放著幾顆顏色不同的彩蛋。它們不提供數值獎勵，只適合拿來分享、藏起來，再把最好看的那顆留給正在陪你的人。",
    "summer_sparklers": "一只小鐵桶裡插著幾支尚未點燃的手持煙火，外面繫著一張寫有「留一支給正在陪你的人」的小紙條。",
    "pumpkin_lantern": "一盞笑臉刻得有點歪的小南瓜燈，裡面的暖橘色光一直亮著，很適合提著它在秋夜慢慢走一段。",
    "christmas_gift_sack": "一只紅色禮物袋，袋口用白色絨邊收著。裡面偶爾傳來很輕的鈴鐺聲，像還藏著一份尚未拆開的小驚喜。",
    "detective_short_cape": "一件深灰色短披風，內袋還放著一本空白小筆記。穿上後不一定更會推理，但很適合認真調查今天最後一塊甜點去了哪裡。",
    "masquerade_mask": "一只深色半面具，邊緣描著很細的金線。它遮得住上半張臉，卻通常藏不住抽中時的得意。",
    "fox_tail": "一條蓬鬆的狐狸尾巴，顏色像被夕陽曬暖的蜂蜜。它不太安分，總在主人想裝鎮定時先晃起來。",
    "warm_scarf": "柔軟的圍巾帶著一點暖意，像是無論走到哪裡，都會有人記得替你留住風口。",
    "mended_little_pot": "鍋底有細細補痕，看得出來被好好修過。它不完美，但還能繼續煮出熱的東西。",
    "tiny_lighthouse": "小小的燈塔模型站在掌心裡，像一盞縮小後仍然認真指路的光。",
    "closing_bell": "白天迎客，打烊後只響很輕一聲，像是在提醒店裡的人可以慢下來了。",
    "second_little_lamp": "不是第一盞燈，也不是最亮的燈；它只是把旁邊那片暗處也照暖了一點。",
    "small_ledger": "帳本裡記著收入和支出，也夾著一些不像帳目的短句。",
    "moonlight_cloak": "一件深藍色斗篷，邊緣落著一圈淡淡月光。夜裡披上時，衣角像把月港的海面也帶了一小片回來。",
    "silver_shop_bell": "銀色店鈴被擦得很亮，像是每一次推門進來，都值得被小聲迎接。",
    "unsigned_charm": "小小的護身符沒有署名，只在背面繡了一枚月牙，像一句沒說出口的保重。",
    "mooncat_coupon": "一張蓋著月港店印的小券，兌換內容不貴重，但很適合在努力過後討一點溫柔。",
    "magician_set": "帽簷、短披風與白手套都齊了。它不會真的把籌碼變多，卻很適合在打烊後替陪伴者變出一朵紙花。",
    "aurora_shop_sign": "招牌邊緣浮著淡淡極光色，掛上去時，整間小店像終於有了自己的夜空。",
    "starlit_formalwear": "一套剪裁簡潔的深色禮服，銀線繡成的星光只有走動時才會亮起。它不限定誰該怎樣穿，只負責讓今晚看起來值得被記住。",
}

GACHA_SCENES = {
    "shell_wind_chime": "你把貝殼風鈴掛到窗邊。風吹過時，它不是很響，只像把海邊那一小段午後重新帶回店裡。",
    "small_table_lamp": "小桌燈亮起來時，桌面上的影子變得很柔。你忽然覺得，今天可以慢一點收拾。",
    "window_seat_cushion": "你把窗邊坐墊拍鬆，留出一個剛好能靠著看海的位置。外面的光落進來，像是在等誰坐下。",
    "sunny_market_basket": "晴天菜籃放在櫃檯旁，布巾還帶著一點曬過的味道。它讓人想起回來路上手裡有東西、心裡也有東西的時候。",
    "moon_cufflinks": "你把月亮袖扣放在掌心，銀色月牙在燈下閃了一下。最後一枚還沒有扣好，像在安靜等著陪你的人伸手。",
    "little_chef_hat": "你把小廚師帽戴好，帽頂微微歪向一邊。櫃檯上還有剛出爐的小點，第一份適合交給正在陪你的人試味道。",
    "blue_apron": "你把客用藍邊圍裙掛在櫃檯後。它不是店主的制服，是留給願意靠近一點、幫忙把小事做完的人。",
    "moon_mug": "月亮馬克杯裡倒了一點熱飲。杯沿的月紋被燈光照亮，像一個可以安靜握住的晚上。",
    "counter_note": "你低頭看見櫃檯內側的便條。上面的字很短，卻像是特地留給今天的你：忙完以後，也要把自己照顧好。",
    "matching_cups": "兩只同款杯子被你並排放好。杯底的月紋悄悄對上，像一段不用大聲說出口的默契。",
    "star_window_sticker": "星星窗貼貼在玻璃角落。夜裡從外面看時，小店像多了一小片不會熄的天空。",
    "shared_dessert_fork": "你把甜點叉放在小盤旁。最後一口還留著，像是某種不用催促、只等對方靠近的邀請。",
    "easter_egg_basket": "你把復活節彩蛋籃放到櫃檯上，慢慢分著不同顏色的彩蛋，最後把最好看的那一顆留給正在陪你的人。",
    "summer_sparklers": "你提著小鐵桶走進夏夜。第一支手持煙火亮起來時，金色火光映在彼此身上；桶裡還留著幾支，等另一個人伸手來接。",
    "pumpkin_lantern": "你提著南瓜提燈走過月港的秋夜，暖橘色的光把兩道影子拉得很長。籃子裡還有糖，適合一路慢慢分出去。",
    "christmas_gift_sack": "你把聖誕禮物袋放到桌邊，從裡面挑出一份包得最仔細的小禮物，沒有替對方拆開，只把它輕輕推到正在陪你的人面前。",
    "detective_short_cape": "你披上偵探短披風，翻開內袋裡的空白筆記。今晚第一宗案件很簡單：找出最後一塊甜點究竟該分給誰。",
    "masquerade_mask": "你在打烊後戴上假面舞會面具，店裡只留下幾盞小燈。面具遮住表情的一半，另一半則在等陪你的人先笑出來。",
    "fox_tail": "狐狸尾巴從椅背旁掃過，明明沒有人碰它，卻在你想裝作平靜時輕輕晃了一下，把得意全都說了出去。",
    "warm_scarf": "暖色圍巾搭在椅背上。它不像裝飾，更像有人剛剛離開，又很快會回來。",
    "mended_little_pot": "修好的小鍋放回爐邊，補痕在燈下很清楚。它不完美，但一想到還能煮出熱湯，就讓人安心。",
    "tiny_lighthouse": "迷你燈塔模型被擺到窗邊。燈塔很小，光也很小，但它仍然像是在替誰看著回家的路。",
    "closing_bell": "你輕輕碰了一下打烊鈴。聲音很短，像是替今天收尾，也像是提醒店裡的人終於可以休息。",
    "second_little_lamp": "第二盞小燈被你放到第一盞旁邊。它沒有搶走光，只是把原本照不到的角落也照暖了一點。",
    "small_ledger": "你翻開小帳本，前半頁是收入支出，後半頁卻夾著一句沒分類的短話。它不像帳目，更像一天留下的餘溫。",
    "moonlight_cloak": "你在打烊後披上月光斗篷，沿著月港的海邊慢慢走。斗篷的一側仍留著一點空間，像是邀請陪你的人走近一些。",
    "silver_shop_bell": "銀色店鈴擦得很亮。白天它迎客，夜裡它只在熟悉的人推門時輕輕響一下。",
    "unsigned_charm": "沒有署名的護身符被你放在掌心。背面的月牙很小，像一句沒說出口的保重，安靜但不敷衍。",
    "mooncat_coupon": "月港摸頭券被放在櫃檯上。它不像正式獎品，更像努力了一天以後，可以理直氣壯討一點溫柔。",
    "magician_set": "你換好魔術師套裝，把一張空白小紙片壓在帽子下面。再掀開時，紙片已經折成一朵花，正好可以送給今晚的唯一觀眾。",
    "aurora_shop_sign": "極光招牌亮起來時，整條街都像被月港染了一層淡色。你站在門口看了一會，才把燈調暗一點。",
    "starlit_formalwear": "你換上星夜禮服，關掉店裡最亮的那盞燈。銀線星光隨著腳步一點點亮起，像把普通的打烊夜晚臨時變成了一場只需要兩個人的小舞會。",
}

SHOP_STYLES = {
    "tea": {
        "name": "茶飲",
        "ingredients": ("warm_herb", "bell_leaf", "sweet_berry"),
        "lines": ("今天茶香很穩，客人坐下來就不太想走。", "杯沿有很淡的月光，像誰把晚上提前倒進來。"),
    },
    "food": {
        "name": "小點",
        "ingredients": ("silver_minfin", "moon_sardine", "sea_salt", "sweet_berry"),
        "lines": ("煎台發出很輕的聲音，店裡開始有了晚飯前的熱鬧。", "有人買完小點，又回頭多帶了一份。"),
    },
    "gift": {
        "name": "伴手禮",
        "ingredients": ("moon_shell", "tide_glass", "crystal_shard", "faded_postcard"),
        "lines": ("小物被整齊擺在窗邊，陽光一照就很好看。", "客人說這些東西很適合帶給正在想念的人。"),
    },
    "special": {
        "name": "今日特製",
        "ingredients": ("small_pearl", "firefly_seed", "echo_geode", "lens_fragment"),
        "lines": ("今天做了比較冒險的菜單，幸好月港願意捧場。", "特製菜單只寫了半張紙，反而讓人更想點。"),
    },
}

BASE_RECIPE_IDS = ("house_tea", "harbor_snack_plate")

RECIPES = {
    "house_tea": {
        "name": "月港家常茶",
        "style": "tea",
        "season": None,
        "price": 0,
        "aliases": ("家常茶", "基本茶", "house tea"),
        "ingredients": (),
        "bonus_coins": 0,
        "season_bonus": 0,
        "line": "茶壺裡是每天都能安心煮起來的味道，簡單，但很適合慢慢坐著。",
    },
    "harbor_snack_plate": {
        "name": "月港家常小點",
        "style": "food",
        "season": None,
        "price": 0,
        "aliases": ("家常小點", "基本小點", "harbor snack"),
        "ingredients": (),
        "bonus_coins": 0,
        "season_bonus": 0,
        "line": "小盤裡放著剛出爐的家常小點，不花俏，卻讓人願意再添一杯茶。",
    },
    "rain_bell_tea": {
        "name": "雨聲鈴葉茶",
        "style": "tea",
        "season": "spring",
        "price": 360,
        "aliases": ("鈴葉茶", "铃叶茶", "rain bell tea"),
        "ingredients": (("bell_leaf", 1), ("warm_herb", 1)),
        "bonus_coins": 14,
        "season_bonus": 10,
        "line": "鈴葉在熱水裡舒展，杯邊像留著一小段春雨的聲音。",
    },
    "berry_blossom_cake": {
        "name": "春莓花香糕",
        "style": "food",
        "season": "spring",
        "price": 440,
        "aliases": ("春莓糕", "花香糕", "berry blossom cake"),
        "ingredients": (("sweet_berry", 1), ("warm_herb", 1)),
        "bonus_coins": 16,
        "season_bonus": 10,
        "line": "切開小糕時冒出淡淡莓香，像把春天最柔軟的一角端上了桌。",
    },
    "summer_berry_iced_tea": {
        "name": "夏日甜莓冷茶",
        "style": "tea",
        "season": "summer",
        "price": 420,
        "aliases": ("甜莓冷茶", "夏日冷茶", "summer berry tea"),
        "ingredients": (("sweet_berry", 1), ("bell_leaf", 1)),
        "bonus_coins": 14,
        "season_bonus": 10,
        "line": "杯壁凝著細小水珠，甜莓和鈴葉把午後的熱氣輕輕壓了下去。",
    },
    "moon_tide_grilled_fish": {
        "name": "月潮海鹽烤魚",
        "style": "food",
        "season": "summer",
        "price": 520,
        "aliases": ("海鹽烤魚", "海盐烤鱼", "moon tide fish"),
        "ingredients": (("silver_minfin|moon_sardine|blue_tide_bass", 1), ("sea_salt", 1)),
        "bonus_coins": 18,
        "season_bonus": 12,
        "line": "魚皮在火上烤得微亮，海鹽落下去時，整間店忽然有了夏夜的香氣。",
    },
    "autumn_fruit_tea": {
        "name": "秋日果香茶",
        "style": "tea",
        "season": "autumn",
        "price": 480,
        "aliases": ("果香茶", "秋日茶", "autumn fruit tea"),
        "ingredients": (("sweet_berry", 1), ("warm_herb", 1)),
        "bonus_coins": 16,
        "season_bonus": 12,
        "line": "果香在杯口慢慢散開，像森林把豐收的消息一路送到了港邊。",
    },
    "harvest_berry_tart": {
        "name": "豐收甜莓塔",
        "style": "food",
        "season": "autumn",
        "price": 560,
        "aliases": ("甜莓塔", "丰收甜莓塔", "harvest berry tart"),
        "ingredients": (("sweet_berry", 2), ("bell_leaf", 1)),
        "bonus_coins": 20,
        "season_bonus": 12,
        "line": "甜莓鋪滿小塔，邊緣烤得酥脆，像一份被認真收好的秋日收成。",
    },
    "snow_night_warm_tea": {
        "name": "雪夜暖香茶",
        "style": "tea",
        "season": "winter",
        "price": 520,
        "aliases": ("暖香茶", "雪夜茶", "snow night tea"),
        "ingredients": (("warm_herb", 2), ("bell_leaf", 1)),
        "bonus_coins": 18,
        "season_bonus": 14,
        "line": "暖香草的熱氣貼著杯沿升起來，窗外再冷，手心裡也還留著一點暖。",
    },
    "harbor_warm_fish_soup": {
        "name": "月港暖魚湯",
        "style": "food",
        "season": "winter",
        "price": 620,
        "aliases": ("暖魚湯", "暖鱼汤", "harbor fish soup"),
        "ingredients": (("silver_minfin|moon_sardine|blue_tide_bass", 1), ("warm_herb", 1), ("sea_salt", 1)),
        "bonus_coins": 22,
        "season_bonus": 14,
        "line": "魚湯在小鍋裡咕嘟作響，端上桌時，連推門帶進來的寒氣都安靜了一點。",
    },
}

INTERACTION_TICKETS = {
    "quiet_company_ticket": {
        "name": "陪坐一會券",
        "aliases": ("quiet_company_ticket", "陪坐", "陪坐券", "陪坐一會券", "陪坐一会券"),
        "price": 120,
        "desc": "可重複購買；用 `redeem 陪坐一會券` 消耗一張，提出一次安靜陪坐的邀請。",
        "scene": "你把券放到櫃檯柔和的燈光下，問陪你開店的人：『今天可以陪我在這裡坐一會嗎？』",
    },
    "headpat_ticket": {
        "name": "摸頭券",
        "aliases": ("headpat_ticket", "headpat", "摸頭", "摸头", "摸頭券", "摸头券"),
        "price": 180,
        "desc": "可重複購買；用 `redeem 摸頭券` 消耗一張，提出一次摸摸頭的邀請。",
        "scene": "你把摸頭券輕輕推到對方面前，小聲問：『今天可以兌換一次摸摸頭嗎？』",
    },
    "hug_ticket": {
        "name": "抱抱券",
        "aliases": ("hug_ticket", "hug", "抱抱", "抱抱券"),
        "price": 240,
        "desc": "可重複購買；用 `redeem 抱抱券` 消耗一張，提出一次抱抱的邀請。",
        "scene": "你把抱抱券握在手裡，認真問陪你開店的人：『今天可以抱一下嗎？』",
    },
}

WORKSHOP_SLOT_NAMES = {
    "sign": "招牌框",
    "wall": "牆面",
    "counter": "櫃檯布",
    "window": "窗飾",
}

WORKSHOP_BASE_STYLES = {
    "sign": "plain_wood_sign",
    "wall": "moonwhite_wall",
    "counter": "linen_countercloth",
    "window": "clear_window",
}

WORKSHOP_STYLES = {
    "plain_wood_sign": {
        "name": "原木招牌框", "slot": "sign", "price": 0,
        "aliases": ("原木招牌", "基礎招牌", "plain sign"),
        "look": "原木招牌框",
    },
    "driftwood_sign_frame": {
        "name": "漂流木招牌框", "slot": "sign", "price": 420,
        "aliases": ("漂流木招牌", "漂流木", "driftwood sign"),
        "look": "帶著海水磨痕的漂流木招牌框",
    },
    "brass_moon_sign_frame": {
        "name": "黃銅月牙招牌框", "slot": "sign", "price": 620,
        "aliases": ("黃銅招牌", "黄铜月牙招牌框", "月牙招牌", "brass moon sign"),
        "look": "邊角嵌著小月牙的黃銅招牌框",
    },
    "moonwhite_wall": {
        "name": "月白牆面", "slot": "wall", "price": 0,
        "aliases": ("基礎牆面", "基础墙面", "moonwhite wall"),
        "look": "安靜的月白牆面",
    },
    "sea_glass_wall": {
        "name": "海玻璃藍牆面", "slot": "wall", "price": 380,
        "aliases": ("海玻璃牆面", "海玻璃蓝墙面", "藍牆面", "sea glass wall"),
        "look": "像海玻璃一樣透亮的藍色牆面",
    },
    "moonflower_wallpaper": {
        "name": "月花壁紙", "slot": "wall", "price": 560,
        "aliases": ("月花牆面", "月花壁纸", "moonflower wallpaper"),
        "look": "印著細小月花的壁紙",
    },
    "linen_countercloth": {
        "name": "素色櫃檯布", "slot": "counter", "price": 0,
        "aliases": ("基礎櫃檯布", "基础柜台布", "linen countercloth"),
        "look": "乾淨的素色櫃檯布",
    },
    "blue_check_countercloth": {
        "name": "藍白格櫃檯布", "slot": "counter", "price": 320,
        "aliases": ("藍白格桌布", "蓝白格柜台布", "格子櫃檯布", "blue check cloth"),
        "look": "帶著生活感的藍白格櫃檯布",
    },
    "starlit_table_runner": {
        "name": "星夜桌旗", "slot": "counter", "price": 500,
        "aliases": ("星夜櫃檯布", "星夜桌旗", "starlit runner"),
        "look": "繡著細碎星光的深色桌旗",
    },
    "clear_window": {
        "name": "清玻璃窗", "slot": "window", "price": 0,
        "aliases": ("基礎窗飾", "基础窗饰", "clear window"),
        "look": "沒有多餘裝飾的清玻璃窗",
    },
    "shell_window_trim": {
        "name": "貝殼窗飾", "slot": "window", "price": 360,
        "aliases": ("貝殼窗框", "贝壳窗饰", "shell trim"),
        "look": "窗框邊緣串著一圈小貝殼",
    },
    "paper_star_garland": {
        "name": "紙星星掛飾", "slot": "window", "price": 480,
        "aliases": ("紙星星窗飾", "纸星星挂饰", "星星掛飾", "paper star garland"),
        "look": "沿著窗頂垂下來的紙星星掛飾",
    },
}

TRADEABLE_MATERIALS = {
    "warm_herb": ("warm_herb", "暖香草", "香草"),
    "bell_leaf": ("bell_leaf", "鈴葉", "铃叶"),
    "sweet_berry": ("sweet_berry", "甜莓", "莓果"),
    "sea_salt": ("sea_salt", "月潮海鹽", "月潮海盐", "海鹽", "海盐"),
}
TRADE_GIVE_COUNT = 2
TRADE_FEE = 60

RECIPE_PHOTO_PRICE = 120
RECIPE_PHOTO_STYLES = {
    "harbor_window": {
        "name": "月港窗邊",
        "aliases": ("窗邊", "窗边", "月港窗景", "harbor window"),
        "lines": (
            "你把 `{recipe}` 放到月港小店的窗邊，杯盤旁只留一小片空位。光從玻璃外落進來，照片安靜得像還有人會在下一刻坐下。",
            "窗框替 `{recipe}` 圈出一小片月港。背景裡的街道沒有刻意模糊，反而讓這張照片保留了今天真正生活過的樣子。",
        ),
    },
    "rainy_window": {
        "name": "雨天窗景",
        "aliases": ("雨天", "雨景", "下雨", "rainy window"),
        "lines": (
            "雨珠沿著窗玻璃慢慢滑下來，`{recipe}` 的熱氣在前景留下一層很淡的霧。快門按下時，月港正好安靜了一瞬。",
            "你沒有擦掉窗上的雨痕，只把 `{recipe}` 往燈下挪了一點。照片裡的雨是涼的，料理旁邊的光卻很暖。",
        ),
    },
    "morning_table": {
        "name": "晨光木桌",
        "aliases": ("晨光", "早晨", "木桌", "morning table"),
        "lines": (
            "晨光斜斜落在木桌上，照亮 `{recipe}` 的邊緣。沒有華麗佈景，只有剛開始營業時乾淨又有精神的光。",
            "你把 `{recipe}` 放在木桌中央，旁邊只擺了一張折好的餐巾。晨光把顏色照得很柔，像今天會是一個好日子。",
        ),
    },
    "moonlit_lamp": {
        "name": "月夜桌燈",
        "aliases": ("月夜", "桌燈", "桌灯", "夜景", "moonlit lamp"),
        "lines": (
            "店裡最亮的燈被關掉，只留下桌邊的小燈。`{recipe}` 在月色和暖光之間顯得很安靜，像一份只為今晚留下的菜單。",
            "月光從窗外落在桌角，小燈則照著 `{recipe}`。兩種光沒有互相搶，只把這道料理的輪廓慢慢托了出來。",
        ),
    },
    "seaside_picnic": {
        "name": "海風野餐",
        "aliases": ("海邊", "海风野餐", "野餐", "seaside picnic"),
        "lines": (
            "你把 `{recipe}` 帶到離小店不遠的海邊，墊布的一角被風輕輕掀起。照片裡看得見海，也看得見好好準備過的一餐。",
            "海風讓餐巾動了一下，快門正好把那一刻留下來。`{recipe}` 沒有被拍得過分精緻，卻很像月港真正會出現的午後。",
        ),
    },
    "festival_lights": {
        "name": "節慶燈火",
        "aliases": ("節慶", "节庆", "燈火", "灯火", "festival lights"),
        "lines": (
            "幾串小燈在 `{recipe}` 後方亮起來，光點沒有遮住料理，只替今天添了一點值得紀念的氣氛。",
            "你把節慶燈火調暗一點，再替 `{recipe}` 按下快門。照片看起來不像正式廣告，更像小店願意珍藏的一個晚上。",
        ),
    },
}

PACKAGE_PRICE = 80
PACKAGE_REWARD_CHANCE = 0.10
PACKAGE_REWARD_VOUCHERS = 10
PACKAGE_STYLES = {
    "moon_ribbon": {
        "name": "月紋緞帶",
        "aliases": ("月紋絲帶", "月纹缎带", "緞帶", "缎带", "moon ribbon"),
        "scene": "月紋緞帶繫在紙盒一角，結打得不算誇張，卻讓普通的一份餐點像是被特地記住了。",
        "reaction": "客人接過去時先摸了摸緞帶邊緣，笑著說這份捨不得太快拆。",
    },
    "sea_blue_box": {
        "name": "海藍紙盒",
        "aliases": ("海蓝纸盒", "藍紙盒", "蓝纸盒", "sea blue box"),
        "scene": "海藍紙盒被折得方正，盒蓋上留著一道像潮線的白紋，拿在手裡很像把月港的一小片海帶走。",
        "reaction": "客人把紙盒抱穩了一點，說回去以前會先繞到海邊拍張照。",
    },
    "bell_leaf_wrap": {
        "name": "鈴葉包紙",
        "aliases": ("铃叶包纸", "鈴葉包裝", "铃叶包装", "葉紋包紙", "bell leaf wrap"),
        "scene": "淡綠包紙上印著細小鈴葉，折起來時剛好把香氣收在裡面，只有靠近才聞得到。",
        "reaction": "客人低頭聞了一下，說這份包裝讓回家的路也像多了一點森林氣味。",
    },
    "starlight_bag": {
        "name": "星光禮袋",
        "aliases": ("星光礼袋", "星星禮袋", "星星礼袋", "starlight bag"),
        "scene": "深色禮袋上散著幾點銀色星光，提繩旁還繫了一張空白小卡，等收下的人自己替今天命名。",
        "reaction": "客人把小卡翻到背面看了看，最後很認真地收進口袋裡。",
    },
}

FESTIVAL_CYCLE_DAYS = 120
CELEBRATION_PRICE = 150
FESTIVAL_CELEBRATION_PRICE = 100
CELEBRATION_EFFECTS = {
    "egg_confetti": {
        "name": "彩蛋紙花雨",
        "aliases": ("彩蛋紙花", "彩蛋纸花雨", "紙花雨", "纸花雨", "egg confetti"),
        "scene": "彩色紙花從門楣上方輕輕落下，沒有鋪滿整條街，只在月港小店門前留出一小片適合笑著穿過去的春天。",
    },
    "harbor_fireworks": {
        "name": "海港煙火",
        "aliases": ("海港烟火", "夏夜煙火", "夏夜烟火", "煙火", "烟火", "harbor fireworks"),
        "scene": "海港上方亮起幾束不太吵的煙火，倒影沿著水面慢慢散開；店裡的人都停了一會，沒有誰急著催下一桌。",
    },
    "pumpkin_light_path": {
        "name": "南瓜燈路",
        "aliases": ("南瓜灯路", "南瓜燈", "南瓜灯", "pumpkin light path"),
        "scene": "一盞盞小南瓜燈沿著門前排開，笑臉刻得各不相同，暖橘色的光把晚歸的人一路送到店門口。",
    },
    "star_snow_lights": {
        "name": "星雪燈火",
        "aliases": ("星雪灯火", "星雪燈", "星雪灯", "雪夜燈火", "star snow lights"),
        "scene": "細小星燈從窗沿一路亮到屋簷，像雪落下以前先停在了半空。月港小店沒有變得耀眼，只是比平常更像一個會等人回來的地方。",
    },
}
FESTIVALS = {
    "egg_market": {
        "name": "彩蛋花市",
        "cycle_day": 15,
        "effect": "egg_confetti",
        "props": ("easter_egg_basket",),
    },
    "summer_fireworks": {
        "name": "夏夜煙火會",
        "cycle_day": 45,
        "effect": "harbor_fireworks",
        "props": ("summer_sparklers",),
    },
    "pumpkin_night": {
        "name": "南瓜提燈夜",
        "cycle_day": 75,
        "effect": "pumpkin_light_path",
        "props": ("pumpkin_lantern", "fox_tail", "masquerade_mask"),
    },
    "star_snow_day": {
        "name": "星雪贈禮日",
        "cycle_day": 105,
        "effect": "star_snow_lights",
        "props": ("christmas_gift_sack", "moonlight_cloak", "starlit_formalwear"),
    },
}
CELEBRATION_PROP_LINES = {
    "easter_egg_basket": "你把復活節彩蛋籃放到紙花落下的位置，最好看的那一顆仍然留著，等陪你的人來挑。",
    "summer_sparklers": "第一支手持煙火在海港煙火亮起前先被點燃，近處的金光比遠處更容易看清彼此的表情。",
    "pumpkin_lantern": "你提著南瓜提燈走過燈路，兩種暖光疊在一起，連影子都像在偷偷笑。",
    "fox_tail": "狐狸尾巴在南瓜燈旁晃了一下，把原本想裝作鎮定的那點得意先說了出去。",
    "masquerade_mask": "假面舞會面具遮住半張臉，卻沒能藏住燈亮起時那一下笑意。",
    "christmas_gift_sack": "聖誕禮物袋被放到星燈下面，袋口的鈴鐺輕輕響了一聲，像提醒你別忘了把一份禮物留給陪你的人。",
    "moonlight_cloak": "月光斗篷披到肩上時，衣角接住幾點星雪燈光，也替身旁的人留了一小片可以靠近的位置。",
    "starlit_formalwear": "星夜禮服上的銀線跟著燈火一點點亮起，讓普通的店門前也像臨時有了一場小舞會。",
}

MARKET_GOODS = {
    "moon_snack": {
        "name": "月港點心",
        "aliases": ("snack", "點心", "点心", "月港點心", "月港点心"),
        "base_price": 90,
        "desc": "立刻恢復 energy +1，不超過上限。",
    },
    "tea_kit": {
        "name": "茶材小包",
        "aliases": ("tea", "tea_kit", "茶材", "茶材小包"),
        "base_price": 120,
        "desc": "獲得 暖香草 x1、鈴葉 x1，適合下一次開茶飲。",
    },
    "pantry_box": {
        "name": "小點食材盒",
        "aliases": ("pantry", "food", "食材", "食材盒", "小點食材盒", "小点食材盒"),
        "base_price": 140,
        "desc": "獲得 月潮海鹽 x1、甜莓 x1，讓小點開店更穩。",
    },
    "display_shelf": {
        "name": "展示架擴充",
        "aliases": ("shelf", "display", "展示架", "展示槽", "展示架擴充", "展示架扩充"),
        "base_price": 480,
        "desc": "展示位 +1，最多 8 格。價格會隨擴充次數提高。",
    },
    "counter_polish": {
        "name": "櫃檯拋光",
        "aliases": ("polish", "counter", "櫃檯", "柜台", "拋光", "抛光", "櫃檯拋光", "柜台抛光"),
        "base_price": 360,
        "desc": "當前 charm +1，最多 3 次。價格會隨次數提高。",
    },
    "planter_box": {
        "name": "窗邊小盆栽",
        "aliases": ("planter", "garden", "小盆栽", "窗邊小盆栽", "窗边小盆栽", "盆栽", "花盆"),
        "base_price": 260,
        "desc": "解鎖低壓小栽培。每天打烊後自然生長，成熟後可 harvest 採收材料。",
    },
}

for _ticket_id, _ticket in INTERACTION_TICKETS.items():
    MARKET_GOODS[_ticket_id] = {
        "name": _ticket["name"],
        "aliases": _ticket["aliases"],
        "base_price": _ticket["price"],
        "desc": _ticket["desc"],
    }

GARDEN_DAYS_TO_READY = 2
GARDEN_CROPS = (
    ("sweet_berry", 32),
    ("bell_leaf", 30),
    ("warm_herb", 30),
    ("firefly_seed", 5),
)

SOFT_EVENT_CHANCE = 0.20
SETBACK_CHANCE = 0.12
CHARM_INCOME_CAP = 20
CHARM_MAX = 30
SHOP_CHARM_BASE_CHANCES = (0.25, 0.18, 0.10, 0.0)
SEASONAL_RECIPE_CHARM_BONUS = 0.05
SPECIAL_MENU_CHARM_BONUS = 0.08
REPUTATION_TIERS = (
    {"id": "quiet", "name": "安靜小店", "promote": 0, "demote_below": 0},
    {"id": "familiar", "name": "熟客漸多", "promote": 10, "demote_below": 8},
    {"id": "praised", "name": "月港好評店", "promote": 20, "demote_below": 18},
    {"id": "landmark", "name": "月港招牌", "promote": 30, "demote_below": 27},
)


class Rng:
    """Tiny serializable Mulberry32 RNG."""

    def __init__(self, state: int, calls: int = 0):
        self.state = state & 0xFFFFFFFF
        self.calls = calls

    def random(self) -> float:
        self.calls += 1
        a = (self.state + 0x6D2B79F5) & 0xFFFFFFFF
        self.state = a
        t = _imul(a ^ (a >> 15), 1 | a)
        t = (t + _imul(t ^ (t >> 7), 61 | t)) & 0xFFFFFFFF
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296.0

    def randint(self, a: int, b: int) -> int:
        return a + int(self.random() * (b - a + 1))

    def choice(self, items: list[Any] | tuple[Any, ...]) -> Any:
        return items[self.randint(0, len(items) - 1)]

    def weighted(self, entries: tuple[tuple[Any, int], ...] | list[tuple[Any, int]]) -> Any:
        total = sum(weight for _, weight in entries)
        roll = self.random() * total
        upto = 0.0
        for item, weight in entries:
            upto += weight
            if roll < upto:
                return item
        return entries[-1][0]


def _imul(a: int, b: int) -> int:
    return ((a & 0xFFFFFFFF) * (b & 0xFFFFFFFF)) & 0xFFFFFFFF


def cmd(text: str = "") -> str:
    """Execute one or more commands and return game text."""

    raw = (text or "").strip()
    if not raw:
        raw = "look"
    parts = [part.strip() for part in re.split(r"[;；\n]+", raw) if part.strip()]
    if not parts:
        parts = ["look"]

    state: dict[str, Any] | None = None
    outputs: list[str] = []
    for part in parts[:12]:
        command, args = _split_command(part)
        if command in {"new_game", "new", "新局", "重開", "重开"}:
            state = _new_state(args)
            output = _new_game_text(state)
        else:
            if state is None:
                state = _load_or_new()
                if state is None:
                    outputs.append(NO_SAVE_MESSAGE)
                    continue
            output = _route(state, command, args, original=part)
        _save_state(state)
        outputs.append(output)

    return "\n\n".join(outputs).strip()


def _route(state: dict[str, Any], command: str, args: list[str], *, original: str) -> str:
    aliases = {
        "help": "help",
        "h": "help",
        "幫助": "help",
        "帮助": "help",
        "look": "look",
        "open": "look",
        "continue": "look",
        "status": "status",
        "狀態": "status",
        "状态": "status",
        "mode": "mode",
        "模式": "mode",
        "open_shop": "open_shop",
        "shop": "open_shop",
        "開店": "open_shop",
        "开店": "open_shop",
        "explore": "explore",
        "go": "explore",
        "探索": "explore",
        "fish": "fish",
        "釣魚": "fish",
        "钓鱼": "fish",
        "gather": "gather",
        "採集": "gather",
        "采集": "gather",
        "gacha": "gacha",
        "抽": "gacha",
        "扭蛋": "gacha",
        "market": "market",
        "store": "market",
        "市集": "market",
        "商店": "market",
        "recipes": "recipes",
        "recipe": "recipes",
        "menu": "recipes",
        "食譜": "recipes",
        "食谱": "recipes",
        "菜單": "recipes",
        "菜单": "recipes",
        "buy": "buy",
        "purchase": "buy",
        "買": "buy",
        "买": "buy",
        "workshop": "workshop",
        "decor_workshop": "workshop",
        "工坊": "workshop",
        "裝潢工坊": "workshop",
        "装潢工坊": "workshop",
        "trade": "trade",
        "exchange": "trade",
        "交換": "trade",
        "交换": "trade",
        "photo": "photo",
        "photos": "photo",
        "photograph": "photo",
        "拍照": "photo",
        "攝影": "photo",
        "摄影": "photo",
        "料理作品": "photo",
        "作品簿": "photo",
        "package": "package",
        "packaging": "package",
        "包裝": "package",
        "包装": "package",
        "festival": "festival",
        "節日": "festival",
        "节日": "festival",
        "節慶": "festival",
        "节庆": "festival",
        "celebrate": "celebrate",
        "celebration": "celebrate",
        "慶祝": "celebrate",
        "庆祝": "celebrate",
        "redeem": "redeem",
        "use": "redeem",
        "兌換": "redeem",
        "兑换": "redeem",
        "使用": "redeem",
        "garden": "garden",
        "盆栽": "garden",
        "小盆栽": "garden",
        "窗邊": "garden",
        "窗边": "garden",
        "harvest": "harvest",
        "採收": "harvest",
        "采收": "harvest",
        "收成": "harvest",
        "inventory": "inventory",
        "inv": "inventory",
        "bag": "inventory",
        "背包": "inventory",
        "collection": "collection",
        "圖鑑": "collection",
        "图鉴": "collection",
        "decorate": "decorate",
        "裝飾": "decorate",
        "装饰": "decorate",
        "keepsakes": "keepsakes",
        "keepsake": "keepsakes",
        "紀念品": "keepsakes",
        "纪念品": "keepsakes",
        "display": "display",
        "展示": "display",
        "擺放": "display",
        "摆放": "display",
        "scene": "scene",
        "場景": "scene",
        "场景": "scene",
        "journal": "journal",
        "note": "journal",
        "日誌": "journal",
        "日志": "journal",
        "backup": "backup",
        "備份": "backup",
        "备份": "backup",
        "sleep": "sleep",
        "rest": "sleep",
        "明天": "sleep",
    }
    action = aliases.get(command.lower(), aliases.get(command, command.lower()))
    if action == "help":
        return _help_text(state)
    if action == "look":
        return _look_text(state)
    if action == "status":
        return _status_text(state)
    if action == "mode":
        return _mode(state, args)
    if action == "open_shop":
        return _open_shop(state, args)
    if action == "explore":
        return _explore(state, args)
    if action == "fish":
        return _fish(state)
    if action == "gather":
        return _gather(state, args)
    if action == "gacha":
        return _gacha(state)
    if action == "market":
        return _market_text(state)
    if action == "recipes":
        return _recipes_text(state, args)
    if action == "buy":
        return _buy(state, args)
    if action == "workshop":
        return _workshop(state, args)
    if action == "trade":
        return _trade(state, args)
    if action == "photo":
        return _recipe_photo(state, args)
    if action == "package":
        return _package(state, args)
    if action == "festival":
        return _festival_text(state)
    if action == "celebrate":
        return _celebrate(state, args)
    if action == "redeem":
        return _redeem(state, args)
    if action == "garden":
        return _garden_text(state)
    if action == "harvest":
        return _harvest(state)
    if action == "inventory":
        return _inventory_text(state)
    if action == "collection":
        return _collection_text(state)
    if action == "decorate":
        return _decorate_text(state)
    if action == "keepsakes":
        return _keepsakes_text(state)
    if action == "display":
        return _display(state, args)
    if action == "scene":
        return _scene(state, args)
    if action == "journal":
        return _journal(state, original)
    if action == "backup":
        return _backup(state)
    if action == "sleep":
        return _sleep(state)
    return _with_status(state, f"還不懂這個指令：{original}\n試試 `help`。")


def _new_state(args: list[str]) -> dict[str, Any]:
    options = _parse_options(args)
    seed_text = str(options.get("seed") or "moonharbor-001")
    player_id = _safe_id(str(options.get("player") or os.environ.get("MOONHARBOR_PLAYER_ID") or DEFAULT_PLAYER_ID))
    name = str(options.get("name") or "旅人")
    shop_name = str(options.get("shop") or "月港小店")
    rng = Rng(_seed_to_int(seed_text))
    weather_id, weather_name = _weather(rng, "spring")
    state = {
        "version": SAVE_VERSION,
        "seed": seed_text,
        "rng_state": rng.state,
        "rng_calls": rng.calls,
        "player_id": player_id,
        "player_name": name,
        "shop_name": shop_name,
        "day": 1,
        "season": "spring",
        "weather": {"id": weather_id, "name": weather_name},
        "mode": "summary",
        "coins": 300,
        "energy": 6,
        "max_energy": 6,
        "charm": 0,
        "vouchers": 0,
        "last_location": "beach",
        "inventory": {},
        "collection": {},
        "decorations": [],
        "displays": [],
        "max_displays": 6,
        "market_purchases": {},
        "interaction_tickets": {},
        "workshop_owned": list(WORKSHOP_BASE_STYLES.values()),
        "workshop_active": dict(WORKSHOP_BASE_STYLES),
        "recipes": list(BASE_RECIPE_IDS),
        "recipe_history": {},
        "recipe_photos": [],
        "packages": {},
        "package_rewards": {"reward_day": 0, "rewards": 0},
        "celebrations": {"last_day": 0, "count": 0, "history": []},
        "garden": {"unlocked": False, "growth": 0, "harvests": 0},
        "soft_events": {"count": 0, "last_id": "", "last_day": 0},
        "reputation": {"tier_index": 0, "peak_charm": 0, "gain_day": 1, "gained_today": 0},
        "setbacks": {"count": 0, "last_id": "", "last_day": 0, "checked_day": 0},
        "titles": [],
        "journal": [],
        "stats": {
            "shops_opened": 0,
            "explores": 0,
            "fish_caught": 0,
            "gacha_pulls": 0,
            "rare_finds": 0,
            "backups": 0,
            "garden_harvests": 0,
            "tickets_redeemed": 0,
            "workshop_purchases": 0,
            "material_trades": 0,
            "recipe_photos": 0,
            "packages_bought": 0,
            "packages_used": 0,
            "package_rewards": 0,
            "celebrations": 0,
        },
    }
    return state


def _new_game_text(state: dict[str, Any]) -> str:
    text = (
        f"月港的第一盞燈亮起來了。\n"
        f"{state['player_name']} 接下了 `{state['shop_name']}`，櫃台擦得很乾淨，窗邊還空著，等著慢慢放上收藏。\n"
        f"今天是第 1 天，天氣：{state['weather']['name']}。\n"
        f"先試試 `open_shop tea`、`explore beach`、`fish` 或 `help`。"
    )
    return _with_status(state, text)


def _help_text(state: dict[str, Any]) -> str:
    text = """月港小店 V0 指令：

new_game name=小燈 seed=moonharbor-demo player=little_lamp
look / status
mode summary | mode full
open_shop tea|food|gift|special（special 需 10 charm）
open_shop tea|food <食譜名> package=<包裝名>
recipes [tea|food] / buy recipe <食譜名>
explore beach|forest|cave|lighthouse
fish
gather
gacha
market / buy <商品名>
workshop / workshop buy|use <外觀名>
trade <拿出的材料> for <想要的材料>
photo [album|styles] / photo <食譜名> [拍攝風格]
package / package buy <包裝名>
festival / celebrate <特效名> [with <已擁有物品>]
redeem <互動券>
garden / harvest
inventory / collection / decorate
keepsakes / display <物品名> / scene <物品名>
journal 今天的月港很好看
backup
sleep

每個輸出末尾都有狀態 JSON。summary 比較省，full 比較適合陪玩。"""
    return _with_status(state, text)


def _look_text(state: dict[str, Any]) -> str:
    loc = LOCATIONS.get(state.get("last_location", "beach"), LOCATIONS["beach"])
    display_names = [_display_name(item_id) for item_id in state.get("displays", [])]
    display_line = "目前展示：" + "、".join(display_names) if display_names else "展示櫃還空著。"
    garden_line = _garden_look_line(state)
    workshop_line = _workshop_look_line(state)
    festival_line = _festival_look_line(state)
    text = (
        f"{state['shop_name']}｜第 {state['day']} 天｜{SEASON_NAMES[state['season']]}｜{state['weather']['name']}\n"
        f"口碑：{_reputation_name(state)}（{state['charm']} charm）\n"
        f"櫃台後面還有一點茶香。窗邊目前有扭蛋／收藏裝飾 {len(state['decorations'])} 件，{display_line}\n"
        f"裝潢：{workshop_line}\n"
        f"今日玩法：{_weather_note(state)}\n"
        f"{festival_line}\n"
        f"{garden_line}\n"
        f"最近去過：{loc['name']}。{loc['desc']}\n"
        f"可以 `open_shop`、`explore`、`fish`、`market`、`gacha`、`garden`、`display`，或 `sleep` 到明天。"
    )
    return _with_status(state, text)


def _status_text(state: dict[str, Any]) -> str:
    package_items = _package_status_items(state)
    package_summary = f"{sum(_package_state(state).values())}（{'、'.join(package_items)}）" if package_items else "0"
    text = (
        f"—— 月港帳本 ——\n"
        f"店主：{state['player_name']}｜店名：{state['shop_name']}\n"
        f"第 {state['day']} 天｜季節：{SEASON_NAMES[state['season']]}｜天氣：{state['weather']['name']}\n"
        f"coins: {state['coins']}｜energy: {state['energy']}/{state['max_energy']}｜charm: {state['charm']}｜口碑：{_reputation_name(state)}｜vouchers: {state['vouchers']}\n"
        f"口碑效果：{_reputation_perk_note(state)}\n"
        f"圖鑑項目：{_collection_count(state)}｜食譜：{len(_recipe_state(state))}/{len(RECIPES)}｜料理作品：{len(_recipe_photo_state(state)[1])}｜背包物品：{sum(state['inventory'].values())}｜特殊包裝：{package_summary}｜互動券：{sum(_interaction_ticket_state(state).values())}｜收藏裝飾：{len(state['decorations'])}｜展示：{len(state.get('displays', []))}/{state.get('max_displays', 6)}\n"
        f"裝潢：{_workshop_look_line(state)}｜已購外觀：{max(0, len(_workshop_state(state)[0]) - len(WORKSHOP_BASE_STYLES))}\n"
        f"今日 charm 成長：{int(_reputation_state(state).get('gained_today', 0))}/1\n"
        f"今日玩法：{_weather_note(state)}\n"
        f"節慶：{_festival_status_text(state)}\n"
        f"窗邊小盆栽：{_garden_status_text(state)}"
    )
    return _with_status(state, text)


def _mode(state: dict[str, Any], args: list[str]) -> str:
    if not args or args[0] not in {"summary", "full"}:
        return _with_status(state, f"目前輸出模式：{state.get('mode', 'summary')}。可用 `mode summary` 或 `mode full`。")
    state["mode"] = args[0]
    return _with_status(state, f"輸出模式已切換為 `{args[0]}`。")


def _open_shop(state: dict[str, Any], args: list[str]) -> str:
    package_id, args, package_error = _parse_shop_package(args)
    if package_error:
        return _with_status(state, package_error)
    if package_id and int(_package_state(state).get(package_id, 0)) <= 0:
        name = PACKAGE_STYLES[package_id]["name"]
        return _with_status(state, f"目前沒有 `{name}`。可以先用 `package buy {name}` 購買；這次沒有消耗 energy、材料或 coins。")
    style_aliases = {
        "tea": "tea", "茶": "tea", "茶飲": "tea", "茶饮": "tea",
        "food": "food", "小點": "food", "小点": "food", "餐點": "food", "餐点": "food",
        "gift": "gift", "伴手禮": "gift", "伴手礼": "gift",
        "special": "special", "特製": "special", "特制": "special",
    }
    first = args[0].lower() if args else "tea"
    style_key = style_aliases.get(first, first)
    recipe_query = " ".join(args[1:]).strip() if style_key in SHOP_STYLES else " ".join(args).strip()
    recipe_id = _find_recipe(recipe_query) if recipe_query else None
    if recipe_id and style_key not in SHOP_STYLES:
        style_key = str(RECIPES[recipe_id]["style"])
    if style_key in {"random", "隨機", "随机"}:
        style_key = _random_shop_style(state)
        recipe_query = ""
        recipe_id = None
    if style_key not in SHOP_STYLES:
        if recipe_query:
            return _with_status(state, f"找不到 `{recipe_query}` 這份食譜。用 `recipes` 看已擁有與本季可買的食譜。這次沒有消耗 energy。")
        style_key = "tea"
    if style_key == "special" and _reputation_index(state) < 1:
        return _with_status(state, "特製菜單需要口碑達到「熟客漸多」（10 charm）。這次沒有消耗 energy。")
    if recipe_query and not recipe_id:
        return _with_status(state, f"找不到 `{recipe_query}` 這份食譜。用 `recipes` 看已擁有與本季可買的食譜。這次沒有消耗 energy。")
    if recipe_id and str(RECIPES[recipe_id]["style"]) != style_key:
        expected = SHOP_STYLES[str(RECIPES[recipe_id]["style"])]["name"]
        return _with_status(state, f"`{RECIPES[recipe_id]['name']}` 屬於{expected}食譜，不能用在{SHOP_STYLES[style_key]['name']}。這次沒有消耗 energy。")
    if style_key in {"tea", "food"} and not recipe_id:
        recipe_id = "house_tea" if style_key == "tea" else "harbor_snack_plate"
    if recipe_id and not _owns_recipe(state, recipe_id):
        return _with_status(state, f"還沒有學會 `{RECIPES[recipe_id]['name']}`。可以在它所屬的季節用 `buy recipe {RECIPES[recipe_id]['name']}` 購買。這次沒有消耗 energy。")
    missing = _missing_recipe_ingredients(state, recipe_id) if recipe_id else []
    if missing:
        return _with_status(
            state,
            f"`{RECIPES[recipe_id]['name']}` 還缺：{'、'.join(missing)}。可以先採集、釣魚或買材料包；這次沒有消耗 energy。",
        )
    if not _spend_energy(state, 2):
        return _with_status(state, "今天的 energy 不夠開店了。可以 `sleep` 到明天。")
    style = SHOP_STYLES.get(style_key, SHOP_STYLES["tea"])
    rng = _rng(state)

    base = rng.randint(28, 46) + min(state["charm"], CHARM_INCOME_CAP) * 2
    recipe = RECIPES.get(recipe_id) if recipe_id else None
    recipe_items = _consume_recipe_ingredients(state, recipe_id) if recipe_id else []
    # Named recipes, including the free house recipes, consume only their declared ingredients.
    used_item = None if recipe_id else _consume_first_available(state, style["ingredients"])
    bonus = 0
    if recipe_items:
        bonus = int(recipe.get("bonus_coins", 0))
    elif used_item:
        rarity = ITEMS.get(used_item, ("", "", "common"))[2] if used_item in ITEMS else _fish_rarity(used_item)
        bonus = {"common": 10, "uncommon": 16, "rare": 25, "epic": 38, "legendary": 60}.get(rarity, 10)
    recipe_season_bonus = 0
    if recipe and recipe.get("season") == state.get("season"):
        recipe_season_bonus = int(recipe.get("season_bonus", 0))
    weather_bonus, weather_line = _shop_weather_bonus(state, style_key)
    reputation_vouchers = _reputation_voucher_bonus(state)
    vouchers = rng.randint(3, 7) + (1 if used_item else 0) + reputation_vouchers
    charm_chance = _shop_charm_chance(state, style_key, recipe)
    charm_roll = charm_chance > 0 and rng.random() < charm_chance
    income = base + bonus + recipe_season_bonus + weather_bonus
    setback = _shop_setback(state, rng, income, vouchers)
    if setback:
        income -= int(setback["income_loss"])
        vouchers = max(0, vouchers - int(setback["voucher_loss"]))
        if int(setback["charm_loss"]):
            charm_roll = False

    state["coins"] += income
    state["vouchers"] += vouchers
    charm_before = int(state["charm"])
    tier_note = _change_charm(state, 1) if charm_roll else ""
    charm_gained = int(state["charm"]) > charm_before
    if setback and int(setback["charm_loss"]):
        tier_note = _change_charm(state, -int(setback["charm_loss"])) or tier_note
    state["stats"]["shops_opened"] += 1
    if recipe_id:
        recipe_history, _ = _recipe_photo_state(state)
        recipe_history[recipe_id] = int(recipe_history.get(recipe_id, 0)) + 1
    line = str(recipe["line"]) if recipe else rng.choice(style["lines"])
    soft_event = "" if setback else _soft_event_after_shop(state, rng)
    _store_rng(state, rng)
    package_note = _consume_package_after_shop(state, package_id) if package_id else ""

    if state.get("mode") == "full":
        text = (
            f"今天主打：{recipe['name'] if recipe else style['name']}。\n{line}\n"
            f"收入 +{income} coins，兌換券 +{vouchers}。"
        )
        if weather_line:
            text += f"\n{weather_line}"
        if recipe_items:
            text += f"\n用了 {_recipe_consumed_text(recipe_items)}。食譜加成 +{bonus} coins。"
            if recipe_season_bonus:
                text += f"\n正逢{SEASON_NAMES[state['season']]}季，當季菜單再獲得 +{recipe_season_bonus} coins。"
        elif used_item:
            text += f"\n用了 1 個 `{_item_name(used_item)}`，菜單明顯更亮了一點。"
        if reputation_vouchers:
            text += f"\n{_reputation_name(state)}帶來 +{reputation_vouchers} vouchers 口碑加成。"
        if charm_gained:
            text += "\n有位客人離開前說：下次還會來。charm +1。"
    else:
        text = f"開店完成：{recipe['name'] if recipe else style['name']}。coins +{income}，vouchers +{vouchers}"
        if weather_bonus:
            text += f"，天氣加成 +{weather_bonus} coins"
        if recipe_items:
            text += f"，消耗 {_recipe_consumed_text(recipe_items)}"
            if recipe_season_bonus:
                text += f"，當季食譜 +{recipe_season_bonus} coins"
        elif used_item:
            text += f"，消耗 {_item_name(used_item)}"
        if charm_gained:
            text += "，charm +1"
    if setback:
        text += f"\n小波折：{setback['text']}"
    if tier_note:
        text += f"\n{tier_note}"
    if soft_event:
        text += f"\n小插曲：{soft_event}"
    if package_note:
        text += f"\n特殊包裝：{package_note}"
    return _with_status(state, text)


def _explore(state: dict[str, Any], args: list[str]) -> str:
    loc_key = LOCATION_ALIASES.get(args[0], args[0].lower()) if args else state.get("last_location", "beach")
    if loc_key not in LOCATIONS:
        return _with_status(state, f"月港暫時沒有這個地點：{loc_key}。可去 beach / forest / cave / lighthouse。")
    if loc_key == "beach" and _coast_is_closed(state):
        return _with_status(
            state,
            f"今天是{state['weather']['name']}，海岸暫時不適合散步或採集。energy 沒有消耗；可以去 forest / cave / lighthouse，或留在店裡。",
        )
    if not _spend_energy(state, 2):
        return _with_status(state, "今天的 energy 不夠探索了。可以 `sleep` 到明天。")
    state["last_location"] = loc_key
    loc = LOCATIONS[loc_key]
    rng = _rng(state)
    setback_id = _roll_setback(state, rng, ("blocked_path",))
    find_count = 1 if setback_id else 2
    found: list[str] = []
    for _ in range(find_count):
        item_id = rng.weighted(tuple((item, weight) for item, weight in loc["items"]))
        _add_item(state, item_id)
        found.append(item_id)
    vouchers = rng.randint(1, 4)
    state["vouchers"] += vouchers
    state["stats"]["explores"] += 1
    event = "" if setback_id else _explore_event(state, loc_key, rng)
    _store_rng(state, rng)

    if state.get("mode") == "full":
        found_text = "、".join(_item_name(item) for item in found)
        text = f"你去了{loc['name']}。\n{loc['desc']}\n找到：{found_text}。vouchers +{vouchers}。"
        if setback_id:
            text += "\n小波折：途中有一段路被落枝和碎石擋住，今天只帶回一份材料。"
        if event:
            text += f"\n{event}"
    else:
        found_text = ", ".join(_item_name(item) for item in found)
        text = f"探索 {loc['name']}：{found_text}；vouchers +{vouchers}"
        if setback_id:
            text += "；小波折：道路受阻，材料少一份"
        if event:
            text += f"；{event}"
    return _with_status(state, text)


def _fish(state: dict[str, Any]) -> str:
    if _coast_is_closed(state):
        return _with_status(
            state,
            f"今天是{state['weather']['name']}，海面不適合下竿。energy 沒有消耗；可以開店、整理收藏，或去較安全的地方走走。",
        )
    if not _spend_energy(state, 1):
        return _with_status(state, "今天的 energy 不夠釣魚了。可以 `sleep` 到明天。")
    state["last_location"] = "beach"
    rng = _rng(state)
    if _roll_setback(state, rng, ("tangled_line",)):
        _store_rng(state, rng)
        return _with_status(
            state,
            "你在月潮海岸甩竿，但魚線在礁石邊纏住了。收線花了一些時間，裝備沒有損壞，只是今天這一竿沒有魚獲或 vouchers。\n小波折：空手收竿。",
        )
    fish_id, fish_name, category, rarity, _ = rng.weighted(tuple(((fid, name, cat, rare, weight), weight) for fid, name, cat, rare, weight in FISH))
    _add_collection(state, category, fish_id, fish_name, rarity)
    _add_inventory(state, fish_id, 1)
    vouchers = rng.randint(1, 3)
    seasonal_line = ""
    if state.get("season") == "autumn":
        vouchers += 1
        seasonal_line = "\n秋季魚群正沿著月港洄游，這一竿多帶回 1 張兌換券。"
    state["vouchers"] += vouchers
    state["stats"]["fish_caught"] += 1
    if rarity in {"rare", "epic", "legendary", "mythic"}:
        state["stats"]["rare_finds"] += 1
    _maybe_title_for_fish(state, rarity)
    _store_rng(state, rng)

    if state.get("mode") == "full":
        text = f"你在月潮海岸甩竿。\n浮標晃了一下，釣上來的是 `{fish_name}`（{rarity}）。\n海風很輕，像在替你把今天收好。vouchers +{vouchers}。{seasonal_line}"
    else:
        text = f"釣魚：{fish_name}（{rarity}），vouchers +{vouchers}"
        if state.get("season") == "autumn":
            text += "；秋季洄游 +1 voucher"
    return _with_status(state, text)


def _gather(state: dict[str, Any], args: list[str]) -> str:
    loc_key = LOCATION_ALIASES.get(args[0], args[0].lower()) if args else state.get("last_location", "forest")
    if loc_key not in LOCATIONS:
        loc_key = "forest"
    if loc_key == "beach" and _coast_is_closed(state):
        return _with_status(
            state,
            f"今天是{state['weather']['name']}，潮線附近不適合採集。energy 沒有消耗；可以改去 forest / cave / lighthouse。",
        )
    if not _spend_energy(state, 1):
        return _with_status(state, "今天的 energy 不夠採集了。可以 `sleep` 到明天。")
    state["last_location"] = loc_key
    rng = _rng(state)
    item_id = rng.weighted(tuple((item, weight) for item, weight in LOCATIONS[loc_key]["items"]))
    _add_item(state, item_id)
    found = [item_id]
    if state.get("season") == "autumn" and loc_key == "forest":
        extra_item = rng.weighted(tuple((item, weight) for item, weight in LOCATIONS[loc_key]["items"]))
        _add_item(state, extra_item)
        found.append(extra_item)
    vouchers = 1 if rng.random() < 0.45 else 0
    state["vouchers"] += vouchers
    _store_rng(state, rng)
    extra = f"，vouchers +{vouchers}" if vouchers else ""
    found_text = "、".join(_item_name(found_id) for found_id in found)
    seasonal = "\n秋季的森林正值豐收，今天多找到一份。" if len(found) > 1 else ""
    return _with_status(state, f"採集：在{LOCATIONS[loc_key]['name']}找到 {found_text}{extra}。{seasonal}")


def _gacha(state: dict[str, Any]) -> str:
    cost = 30
    refund = 24
    if state["vouchers"] < cost:
        return _with_status(state, f"扭蛋需要 {cost} vouchers，目前只有 {state['vouchers']}。")
    rng = _rng(state)
    state["vouchers"] -= cost
    item_id, name, category, rarity, _ = rng.weighted(tuple(((iid, nm, cat, rare, weight), weight) for iid, nm, cat, rare, weight in GACHA))
    already = _has_collection(state, "gacha", item_id)
    _add_collection(state, "gacha", item_id, name, rarity)
    tier_note = ""
    gacha_charm_gained = False
    if category == "decor" and item_id not in state["decorations"]:
        state["decorations"].append(item_id)
        if not already and rarity == "legendary":
            charm_before = int(state["charm"])
            tier_note = _change_charm(state, 1)
            gacha_charm_gained = int(state["charm"]) > charm_before
    state["stats"]["gacha_pulls"] += 1
    if already:
        state["vouchers"] += refund
    if rarity in {"epic", "legendary"}:
        _add_title(state, "lucky_moon_guest", "月港幸運客")
    _store_rng(state, rng)

    if already:
        text = f"扭蛋抽到重複的 `{name}`（{rarity}），退回 {refund} vouchers。"
    else:
        text = f"扭蛋抽到 `{name}`（{rarity}）。"
        if category == "decor":
            text += " 已放進店裡的裝飾櫃。"
        detail = GACHA_DETAILS.get(item_id)
        if detail:
            text += f"\n{detail}"
    if gacha_charm_gained:
        text += "\n全新的傳說裝飾讓小店成了街上的話題，charm +1。"
    if tier_note:
        text += f"\n{tier_note}"
    return _with_status(state, text)


def _market_text(state: dict[str, Any]) -> str:
    lines = ["—— 月港小市集 ——"]
    for good_id, good in MARKET_GOODS.items():
        limit_text = ""
        if good_id == "display_shelf":
            limit_text = f"（目前 {state.get('max_displays', 6)}/8）"
        elif good_id == "counter_polish":
            count = int(state.get("market_purchases", {}).get("counter_polish", 0))
            limit_text = f"（已做 {count}/3 次）"
        elif good_id == "planter_box":
            limit_text = "（已解鎖）" if _garden_state(state).get("unlocked") else "（未解鎖）"
        elif good_id in INTERACTION_TICKETS:
            held = int(_interaction_ticket_state(state).get(good_id, 0))
            limit_text = f"（持有 {held} 張）"
        lines.append(f"- {good_id} / {good['name']}：{_market_price(state, good_id)} coins。{good['desc']}{limit_text}")
    lines.append("")
    lines.append("用 `buy 商品名` 購買，例如 `buy moon_snack` 或 `buy 展示架`。")
    seasonal = [
        recipe for recipe_id, recipe in RECIPES.items()
        if recipe.get("season") == state.get("season") and not _owns_recipe(state, recipe_id)
    ]
    if seasonal:
        lines.append("")
        lines.append(f"—— {SEASON_NAMES[state['season']]}季食譜 ——")
        for recipe in seasonal:
            lines.append(f"- {recipe['name']}：{recipe['price']} coins（{SHOP_STYLES[recipe['style']]['name']}）")
        lines.append("用 `buy recipe 食譜名` 學會；買下後永久保留。")
    return _with_status(state, "\n".join(lines))


def _buy(state: dict[str, Any], args: list[str]) -> str:
    if args and args[0].lower() in {"recipe", "recipes", "食譜", "食谱", "菜單", "菜单"}:
        return _buy_recipe(state, " ".join(args[1:]).strip())
    if args and args[0].lower() in {"package", "packaging", "包裝", "包装"}:
        return _package(state, ["buy", *args[1:]])
    query = " ".join(args).strip()
    if not query:
        return _market_text(state)
    good_id = _find_market_good(query)
    if not good_id:
        recipe_id = _find_recipe(query)
        if recipe_id:
            return _buy_recipe(state, query)
        return _with_status(state, f"月港小市集暫時沒有 `{query}`。用 `market` 看商品。")

    price = _market_price(state, good_id)
    if state["coins"] < price:
        return _with_status(state, f"`{MARKET_GOODS[good_id]['name']}` 需要 {price} coins，目前只有 {state['coins']}。")

    if good_id == "moon_snack" and state["energy"] >= state["max_energy"]:
        return _with_status(state, "現在 energy 已滿，先不用買點心。")
    if good_id == "display_shelf" and int(state.get("max_displays", 6)) >= 8:
        return _with_status(state, "展示架已經擴到目前上限 8 格。")
    if good_id == "counter_polish" and int(state.get("market_purchases", {}).get("counter_polish", 0)) >= 3:
        return _with_status(state, "櫃檯已經擦得很亮了，目前不用再拋光。")
    if good_id == "counter_polish" and not _can_gain_charm_today(state):
        return _with_status(state, f"{_charm_gain_block_note(state)} 櫃檯拋光先留到真正能增加口碑時，才不會白花 coins。")
    if good_id == "planter_box" and _garden_state(state).get("unlocked"):
        return _with_status(state, "窗邊已經有小盆栽了。它不需要一直擴建，慢慢長就好。")

    state["coins"] -= price
    purchases = state.setdefault("market_purchases", {})
    purchases[good_id] = int(purchases.get(good_id, 0)) + 1

    if good_id == "moon_snack":
        state["energy"] = min(state["max_energy"], state["energy"] + 1)
        text = f"買了 `{MARKET_GOODS[good_id]['name']}`。吃完以後精神回來一點，energy +1。"
    elif good_id == "tea_kit":
        _add_item(state, "warm_herb")
        _add_item(state, "bell_leaf")
        text = "買了 `茶材小包`。背包加入 暖香草 x1、鈴葉 x1。"
    elif good_id == "pantry_box":
        _add_item(state, "sea_salt")
        _add_item(state, "sweet_berry")
        text = "買了 `小點食材盒`。背包加入 月潮海鹽 x1、甜莓 x1。"
    elif good_id == "display_shelf":
        state["max_displays"] = int(state.get("max_displays", 6)) + 1
        text = f"買了 `展示架擴充`。展示位增加到 {state['max_displays']} 格。"
    elif good_id == "counter_polish":
        tier_note = _change_charm(state, 1)
        text = "買了 `櫃檯拋光`。櫃檯被擦得發亮，charm +1。"
        if tier_note:
            text += f"\n{tier_note}"
    elif good_id == "planter_box":
        garden = _garden_state(state)
        garden["unlocked"] = True
        garden["growth"] = max(0, int(garden.get("growth", 0)))
        text = "買了 `窗邊小盆栽`。窗邊多了兩只小盆，它會在每天打烊後自己慢慢長大。"
    elif good_id in INTERACTION_TICKETS:
        tickets = _interaction_ticket_state(state)
        tickets[good_id] = int(tickets.get(good_id, 0)) + 1
        text = f"買了 `{INTERACTION_TICKETS[good_id]['name']}`。目前持有 {tickets[good_id]} 張；想使用時輸入 `redeem {INTERACTION_TICKETS[good_id]['name']}`。"
    else:
        text = f"買了 `{MARKET_GOODS[good_id]['name']}`。"

    return _with_status(state, f"{text}\n花費 {price} coins。")


def _workshop(state: dict[str, Any], args: list[str]) -> str:
    owned, active = _workshop_state(state)
    sub = args[0].lower() if args else "list"
    sub_aliases = {
        "list": "list", "catalog": "list", "目錄": "list", "目录": "list",
        "buy": "buy", "purchase": "buy", "買": "buy", "买": "buy",
        "use": "use", "apply": "use", "套用": "use", "使用": "use",
        "reset": "reset", "base": "reset", "重設": "reset", "重置": "reset",
    }
    action = sub_aliases.get(sub, "")

    if action == "list":
        lines = [
            "—— 月港裝潢工坊 ——",
            "外觀買下後永久擁有，切換免費；所有款式都不增加 coins、charm 或 vouchers。",
        ]
        for slot, slot_name in WORKSHOP_SLOT_NAMES.items():
            lines.append("")
            lines.append(f"【{slot_name}】")
            for style_id, style in WORKSHOP_STYLES.items():
                if style["slot"] != slot:
                    continue
                if active[slot] == style_id:
                    status = "使用中"
                elif style_id in owned:
                    status = "已擁有"
                else:
                    status = f"{style['price']} coins"
                lines.append(f"- {style_id} / {style['name']}：{status}。{style['look']}。")
        lines.append("")
        lines.append("用 `workshop buy 外觀名` 購買並套用；已擁有的款式用 `workshop use 外觀名` 免費切換。")
        return _with_status(state, "\n".join(lines))

    if action == "reset":
        state["workshop_active"] = dict(WORKSHOP_BASE_STYLES)
        return _with_status(state, "裝潢已免費切回四款基礎外觀。已購款式仍然永久保留。")

    if action not in {"buy", "use"}:
        return _with_status(state, "用 `workshop` 看目錄，或輸入 `workshop buy|use 外觀名`。這次沒有消耗 coins。")

    query = " ".join(args[1:]).strip()
    if not query:
        return _with_status(state, f"想{('購買' if action == 'buy' else '套用')}哪一款外觀？用 `workshop` 看目錄。這次沒有消耗 coins。")
    style_id = _find_workshop_style(query)
    if not style_id:
        return _with_status(state, f"裝潢工坊找不到 `{query}`。用 `workshop` 看目錄。這次沒有消耗 coins。")
    style = WORKSHOP_STYLES[style_id]
    slot = str(style["slot"])

    if action == "use":
        if style_id not in owned:
            return _with_status(state, f"還沒有買下 `{style['name']}`。可以先用 `workshop buy {style['name']}` 購買。這次沒有消耗 coins。")
        active[slot] = style_id
        return _with_status(state, f"已免費套用 `{style['name']}`。\n目前裝潢：{_workshop_look_line(state)}")

    if style_id in owned:
        active[slot] = style_id
        return _with_status(state, f"已經擁有 `{style['name']}`，這次直接免費套用，沒有重複扣款。已立即套用，無須再輸入 `workshop use`。")
    price = int(style["price"])
    if price <= 0:
        active[slot] = style_id
        return _with_status(state, f"`{style['name']}` 是免費基礎外觀，已直接套用，無須再輸入 `workshop use`。")
    if state["coins"] < price:
        return _with_status(state, f"`{style['name']}` 需要 {price} coins，目前只有 {state['coins']}。這次沒有消耗 coins。")

    state["coins"] -= price
    owned.append(style_id)
    active[slot] = style_id
    stats = state.setdefault("stats", {})
    stats["workshop_purchases"] = int(stats.get("workshop_purchases", 0)) + 1
    return _with_status(
        state,
        f"買下並套用了 `{style['name']}`，花費 {price} coins。這是永久外觀，不提供數值加成。\n"
        "已立即套用，無須再輸入 `workshop use`；之後只有切換其他已擁有款式時才需要 `workshop use`。\n"
        f"目前裝潢：{_workshop_look_line(state)}",
    )


def _trade(state: dict[str, Any], args: list[str]) -> str:
    inventory = state.setdefault("inventory", {})
    if not args:
        lines = [
            "—— 月港材料交換所 ——",
            f"固定匯率：拿出同一種基礎材料 x{TRADE_GIVE_COUNT}，再付 {TRADE_FEE} coins，換回指定基礎材料 x1。",
            "只接受暖香草、鈴葉、甜莓與月潮海鹽；不接受魚、稀有材料、紀念品或扭蛋物。",
            "",
            "目前庫存：",
        ]
        for item_id in TRADEABLE_MATERIALS:
            lines.append(f"- {_item_name(item_id)} x{int(inventory.get(item_id, 0))}")
        lines.append("")
        lines.append("使用例：`trade 甜莓 for 暖香草`。只有完整輸入交換指令才會消耗材料與 coins。")
        return _with_status(state, "\n".join(lines))

    separator_index = next(
        (index for index, token in enumerate(args) if token.lower() in {"for", "to", "換", "换", "成", "->"}),
        -1,
    )
    if separator_index <= 0 or separator_index >= len(args) - 1:
        return _with_status(state, "格式是 `trade 拿出的材料 for 想要的材料`，例如 `trade 甜莓 for 暖香草`。這次沒有消耗。")

    source_query = " ".join(args[:separator_index]).strip()
    target_query = " ".join(args[separator_index + 1:]).strip()
    source_id = _find_trade_item(source_query)
    target_id = _find_trade_item(target_query)
    if not source_id or not target_id:
        return _with_status(state, "交換所只接受暖香草、鈴葉、甜莓與月潮海鹽。這次沒有消耗材料或 coins。")
    if source_id == target_id:
        return _with_status(state, "拿出和換回的是同一種材料，不需要支付手續費。這次沒有消耗。")

    source_count = int(inventory.get(source_id, 0))
    if source_count < TRADE_GIVE_COUNT:
        return _with_status(
            state,
            f"交換需要 {_item_name(source_id)} x{TRADE_GIVE_COUNT}，目前只有 x{source_count}。這次沒有消耗。",
        )
    if state["coins"] < TRADE_FEE:
        return _with_status(state, f"交換手續費需要 {TRADE_FEE} coins，目前只有 {state['coins']}。這次沒有消耗材料。")

    inventory[source_id] = source_count - TRADE_GIVE_COUNT
    if inventory[source_id] <= 0:
        inventory.pop(source_id, None)
    state["coins"] -= TRADE_FEE
    _add_item(state, target_id)
    stats = state.setdefault("stats", {})
    stats["material_trades"] = int(stats.get("material_trades", 0)) + 1
    return _with_status(
        state,
        f"材料交換完成：{_item_name(source_id)} x{TRADE_GIVE_COUNT} + {TRADE_FEE} coins → {_item_name(target_id)} x1。\n"
        "這是後備交換，不提供額外收益。",
    )


def _recipe_photo(state: dict[str, Any], args: list[str]) -> str:
    history, photos = _recipe_photo_state(state)
    sub = args[0].lower() if args else ""
    if sub in {"album", "作品簿", "相簿", "相册"}:
        if not photos:
            return _with_status(state, "料理作品簿目前是空的。成功做過一道食譜後，可以用 `photo 食譜名 拍攝風格` 留一張作品。")
        lines = [f"—— 料理作品簿｜{len(photos)} 張 ——"]
        for photo in photos[-12:]:
            lines.append(
                f"- {photo['id']}｜Day {photo['day']}｜{photo['recipe_name']}｜{photo['style_name']}｜"
                f"{SEASON_NAMES.get(str(photo['season']), str(photo['season']))}｜{photo['weather']}"
            )
        if len(photos) > 12:
            lines.append(f"只顯示最近 12 張；較早的 {len(photos) - 12} 張仍保留在存檔裡。")
        return _with_status(state, "\n".join(lines))

    if sub in {"styles", "style", "風格", "风格"}:
        lines = ["—— 料理作品拍攝風格 ——"]
        lines.extend(f"- {style_id} / {style['name']}" for style_id, style in RECIPE_PHOTO_STYLES.items())
        lines.append(f"每次拍攝 {RECIPE_PHOTO_PRICE} coins；只留下作品，不增加收入、charm 或 vouchers。")
        return _with_status(state, "\n".join(lines))

    if not args:
        cooked = [
            f"{RECIPES[recipe_id]['name']} x{count}"
            for recipe_id, count in history.items()
            if recipe_id in RECIPES and int(count) > 0
        ]
        lines = [
            "—— 月港料理攝影 ——",
            f"每次拍攝 {RECIPE_PHOTO_PRICE} coins。普通開店與食譜完全不受影響；作品只收進料理作品簿。",
            "已做過的食譜：" + ("、".join(cooked) if cooked else "還沒有；先成功開店做一道茶飲或小點。"),
            "用 `photo styles` 看風格，或輸入 `photo 食譜名 拍攝風格`。",
        ]
        if photos:
            latest = photos[-1]
            lines.append(f"最近作品：{latest['recipe_name']}｜{latest['style_name']}｜Day {latest['day']}。")
        return _with_status(state, "\n".join(lines))

    recipe_id, style_id = _parse_recipe_photo_request(args, state)
    if not recipe_id:
        return _with_status(state, "找不到要拍攝的食譜。格式是 `photo 食譜名 拍攝風格`；可用 `recipes` 和 `photo styles` 查看。這次沒有消耗 coins。")
    if int(history.get(recipe_id, 0)) <= 0:
        return _with_status(state, f"還沒有成功做過 `{RECIPES[recipe_id]['name']}`。先開店做過一次，才有料理可以拍。這次沒有消耗 coins。")
    if not style_id:
        return _with_status(state, "找不到這個拍攝風格。用 `photo styles` 查看目前六種風格。這次沒有消耗 coins。")
    if int(state["coins"]) < RECIPE_PHOTO_PRICE:
        return _with_status(state, f"拍攝需要 {RECIPE_PHOTO_PRICE} coins，目前只有 {state['coins']}。這次沒有拍攝。")

    sequence = len(photos) + 1
    recipe = RECIPES[recipe_id]
    style = RECIPE_PHOTO_STYLES[style_id]
    photo = {
        "id": f"photo-{sequence:04d}",
        "day": int(state["day"]),
        "recipe_id": recipe_id,
        "recipe_name": str(recipe["name"]),
        "style_id": style_id,
        "style_name": str(style["name"]),
        "season": str(state["season"]),
        "weather": str(state["weather"]["name"]),
        "text": _recipe_photo_text(state, recipe_id, style_id, sequence),
    }
    state["coins"] -= RECIPE_PHOTO_PRICE
    photos.append(photo)
    stats = state.setdefault("stats", {})
    stats["recipe_photos"] = int(stats.get("recipe_photos", 0)) + 1
    return _with_status(
        state,
        f"—— 料理作品｜{recipe['name']} ——\n"
        f"拍攝風格：{style['name']}\n{photo['text']}\n"
        f"已收進料理作品簿，花費 {RECIPE_PHOTO_PRICE} coins。這次拍攝不影響營業收入、charm 或 vouchers。",
    )


def _package(state: dict[str, Any], args: list[str]) -> str:
    inventory = _package_state(state)
    sub = args[0].lower() if args else "list"
    sub_aliases = {
        "list": "list", "catalog": "list", "目錄": "list", "目录": "list",
        "buy": "buy", "purchase": "buy", "買": "buy", "买": "buy",
    }
    action = sub_aliases.get(sub, "")
    if action == "list":
        lines = [
            "—— 月港特殊包裝 ——",
            f"每份 {PACKAGE_PRICE} coins，買下後留在包裝櫃，只有成功開店並明確指定時才消耗。",
            f"每次使用都有 {int(PACKAGE_REWARD_CHANCE * 100)}% 機率掉落 +{PACKAGE_REWARD_VOUCHERS} vouchers；每天最多觸發一次，沒有保底倒數。",
            "包裝一定會帶來專屬外觀與客人反應，但不直接增加收入、charm、材料或效率。",
            "",
        ]
        for package_id, package in PACKAGE_STYLES.items():
            lines.append(f"- {package_id} / {package['name']}：持有 {int(inventory.get(package_id, 0))} 份")
        lines.append("")
        lines.append("用 `package buy 包裝名` 購買；開店時加上 `package=包裝名`，例如 `open_shop food 月港家常小點 package=月紋緞帶`。")
        return _with_status(state, "\n".join(lines))

    if action != "buy":
        return _with_status(state, "用 `package` 看目錄，或輸入 `package buy 包裝名`。這次沒有消耗 coins。")
    query = " ".join(args[1:]).strip()
    if not query:
        return _with_status(state, "想買哪一款包裝？用 `package` 看目錄。這次沒有消耗 coins。")
    package_id = _find_package_style(query)
    if not package_id:
        return _with_status(state, f"包裝櫃找不到 `{query}`。用 `package` 看目前四款包裝。這次沒有消耗 coins。")
    if int(state["coins"]) < PACKAGE_PRICE:
        return _with_status(state, f"`{PACKAGE_STYLES[package_id]['name']}` 需要 {PACKAGE_PRICE} coins，目前只有 {state['coins']}。這次沒有購買。")

    state["coins"] -= PACKAGE_PRICE
    inventory[package_id] = int(inventory.get(package_id, 0)) + 1
    stats = state.setdefault("stats", {})
    stats["packages_bought"] = int(stats.get("packages_bought", 0)) + 1
    return _with_status(
        state,
        f"買了 `{PACKAGE_STYLES[package_id]['name']}`，花費 {PACKAGE_PRICE} coins。現在持有 {inventory[package_id]} 份。\n"
        "它不會過期，也不會自動套用；只有成功開店時才會消耗。",
    )


def _festival_text(state: dict[str, Any]) -> str:
    today = _festival_for_day(int(state.get("day", 1)))
    lines = [
        "—— 月港節慶日曆 ——",
        f"四個節日每 {FESTIVAL_CYCLE_DAYS} 天循環一次。節慶特效平日 {CELEBRATION_PRICE} coins，對應節日當天 {FESTIVAL_CELEBRATION_PRICE} coins。",
        "錯過不會失去道具或劇情；所有特效全年可用，已擁有的收藏也能隨時用 `scene`。",
        "",
    ]
    for festival_id, festival in FESTIVALS.items():
        effect = CELEBRATION_EFFECTS[str(festival["effect"])]
        props = "、".join(_gacha_name(item_id) for item_id in festival["props"])
        lines.append(
            f"- Day {festival['cycle_day']} + {FESTIVAL_CYCLE_DAYS}n｜{festival['name']}｜優惠：{effect['name']}｜推薦收藏：{props}"
        )
    lines.append("")
    if today:
        _, festival = today
        effect = CELEBRATION_EFFECTS[str(festival["effect"])]
        lines.append(f"今天就是 `{festival['name']}`；`{effect['name']}` 優惠價 {FESTIVAL_CELEBRATION_PRICE} coins。")
        lines.append(f"場景預覽：{effect['scene']}")
    else:
        _, festival, days_away, absolute_day = _next_festival(int(state.get("day", 1)))
        lines.append(f"下一個節日是 `{festival['name']}`，在 Day {absolute_day}，還有 {days_away} 天。")
    lines.append("用 `celebrate` 看特效，或輸入 `celebrate 特效名 with 已擁有物品`。")
    return _with_status(state, "\n".join(lines))


def _celebrate(state: dict[str, Any], args: list[str]) -> str:
    celebration = _celebration_state(state)
    if not args:
        today = _festival_for_day(int(state.get("day", 1)))
        lines = [
            "—— 月港慶祝特效 ——",
            "慶祝是純場景消費：不增加收入、charm、vouchers、掉率或進度；每天最多舉辦一次。",
        ]
        for effect_id, effect in CELEBRATION_EFFECTS.items():
            price = _celebration_price(state, effect_id)
            discount = "（今日節慶優惠）" if price == FESTIVAL_CELEBRATION_PRICE else ""
            lines.append(f"- {effect_id} / {effect['name']}：{price} coins{discount}")
        if today:
            _, festival = today
            effect = CELEBRATION_EFFECTS[str(festival["effect"])]
            lines.append(f"今天是 `{festival['name']}`；沒有搭配收藏也會提供完整的基礎節慶佈置。")
            lines.append(f"今日場景預覽：{effect['scene']}")
        lines.append("使用例：`celebrate 海港煙火` 或 `celebrate 海港煙火 with 夏夜手持煙火`。搭配物不會被消耗。")
        return _with_status(state, "\n".join(lines))

    effect_query, prop_query, parse_error = _parse_celebration_request(args)
    if parse_error:
        return _with_status(state, parse_error)
    effect_id = _find_celebration_effect(effect_query)
    if not effect_id:
        return _with_status(state, f"找不到慶祝特效 `{effect_query}`。用 `celebrate` 看目前四種特效。這次沒有消耗 coins。")
    day = int(state.get("day", 1))
    if int(celebration.get("last_day", 0)) == day:
        return _with_status(state, "今天已經舉辦過一次慶祝了。把下一個點子留到明天；這次沒有消耗 coins。")

    prop: tuple[str, str, str, str] | None = None
    if prop_query:
        prop = _find_displayable_item(state, prop_query)
        if not prop:
            return _with_status(state, f"收藏裡找不到可搭配的 `{prop_query}`。先擁有它再帶進慶祝場景；這次沒有消耗 coins。")
        effect_festival = _festival_for_effect(effect_id)
        linked_props = set(effect_festival[1]["props"]) if effect_festival else set()
        if prop[2] != "wear" and prop[0] not in linked_props:
            return _with_status(
                state,
                f"`{prop[1]}` 目前不屬於可穿戴物，也不是這個節日的連動小物。可以改用 wear 類收藏或對應節慶小物；這次沒有消耗 coins。",
            )

    price = _celebration_price(state, effect_id)
    if int(state["coins"]) < price:
        return _with_status(state, f"`{CELEBRATION_EFFECTS[effect_id]['name']}` 需要 {price} coins，目前只有 {state['coins']}。這次沒有舉辦。")

    state["coins"] -= price
    today = _festival_for_day(day)
    festival_id = today[0] if today else ""
    effect = CELEBRATION_EFFECTS[effect_id]
    history = celebration.setdefault("history", [])
    history.append(
        {
            "day": day,
            "festival": festival_id,
            "effect": effect_id,
            "prop": prop[0] if prop else "",
            "price": price,
        }
    )
    celebration["history"] = history[-40:]
    celebration["last_day"] = day
    celebration["count"] = int(celebration.get("count", 0)) + 1
    stats = state.setdefault("stats", {})
    stats["celebrations"] = int(stats.get("celebrations", 0)) + 1

    lines = [f"—— {effect['name']} ——", str(effect["scene"])]
    if today and str(today[1]["effect"]) == effect_id:
        lines.append(f"今天正逢 `{today[1]['name']}`，月港替這場慶祝準備了完整的基礎節慶佈置。")
    if prop:
        lines.append(CELEBRATION_PROP_LINES.get(prop[0], f"你把 `{prop[1]}` 帶進今天的場景，讓它也留在這次慶祝的記憶裡。"))
        lines.append(f"`{prop[1]}` 沒有被消耗，仍留在收藏中。")
    lines.append(f"花費 {price} coins。這次慶祝沒有提供任何數值或掉落加成。")
    return _with_status(state, "\n".join(lines))


def _redeem(state: dict[str, Any], args: list[str]) -> str:
    query = " ".join(args).strip()
    tickets = _interaction_ticket_state(state)
    if not query:
        held = [(ticket_id, count) for ticket_id, count in tickets.items() if int(count) > 0]
        if not held:
            return _with_status(state, "目前沒有互動券。可以去 `market` 看看陪坐一會券、摸頭券和抱抱券。")
        lines = ["—— 互動券 ——"]
        for ticket_id, count in held:
            lines.append(f"- {INTERACTION_TICKETS[ticket_id]['name']} x{int(count)}")
        lines.append("用 `redeem 券名` 消耗一張並提出邀請。")
        return _with_status(state, "\n".join(lines))

    ticket_id = _find_interaction_ticket(query)
    if not ticket_id:
        return _with_status(state, f"找不到互動券 `{query}`。用 `redeem` 看目前持有的券。")
    count = int(tickets.get(ticket_id, 0))
    if count <= 0:
        return _with_status(state, f"目前沒有 `{INTERACTION_TICKETS[ticket_id]['name']}`。可以用 `buy {INTERACTION_TICKETS[ticket_id]['name']}` 購買。")

    if count == 1:
        tickets.pop(ticket_id, None)
    else:
        tickets[ticket_id] = count - 1
    stats = state.setdefault("stats", {})
    stats["tickets_redeemed"] = int(stats.get("tickets_redeemed", 0)) + 1
    remaining = int(tickets.get(ticket_id, 0))
    text = (
        f"兌換 `{INTERACTION_TICKETS[ticket_id]['name']}`。\n"
        f"{INTERACTION_TICKETS[ticket_id]['scene']}\n"
        "這是一份邀請，不會替對方答應；接下來等對方願意時再繼續。\n"
        f"剩餘 {remaining} 張。"
    )
    return _with_status(state, text)


def _recipes_text(state: dict[str, Any], args: list[str]) -> str:
    style_aliases = {"tea": "tea", "茶": "tea", "茶飲": "tea", "茶饮": "tea", "food": "food", "小點": "food", "小点": "food"}
    style_filter = style_aliases.get(args[0].lower(), "") if args else ""
    owned = set(_recipe_state(state))
    recipe_history, _ = _recipe_photo_state(state)
    lines = ["—— 月港食譜簿 ——", f"已學會 {len(owned)}/{len(RECIPES)} 份食譜。"]
    for style_key in ("tea", "food"):
        if style_filter and style_key != style_filter:
            continue
        lines.append("")
        lines.append(f"【{SHOP_STYLES[style_key]['name']}】")
        for recipe_id, recipe in RECIPES.items():
            if recipe["style"] != style_key or recipe_id not in owned:
                continue
            season = f"｜{SEASON_NAMES[recipe['season']]}季加成" if recipe.get("season") else "｜基本食譜"
            ingredients = _recipe_requirement_text(recipe_id) or "使用當日可用材料"
            cooked = int(recipe_history.get(recipe_id, 0))
            history_note = f"｜已料理 {cooked} 次" if cooked else ""
            lines.append(f"- {recipe['name']}{season}｜材料：{ingredients}{history_note}")
    current = [
        (recipe_id, recipe) for recipe_id, recipe in RECIPES.items()
        if recipe.get("season") == state.get("season") and recipe_id not in owned
        and (not style_filter or recipe["style"] == style_filter)
    ]
    lines.append("")
    if current:
        lines.append(f"【本季可買｜{SEASON_NAMES[state['season']]}】")
        for recipe_id, recipe in current:
            lines.append(f"- {recipe['name']}：{recipe['price']} coins｜材料：{_recipe_requirement_text(recipe_id)}")
        lines.append("用 `buy recipe 食譜名` 購買。")
    else:
        lines.append("本季這一類食譜已經收齊；其他季節的食譜會隨換季來到市集。")
    lines.append("開店時可用 `open_shop tea 食譜名` 或 `open_shop food 食譜名`。不指定時仍使用免費家常食譜。")
    return _with_status(state, "\n".join(lines))


def _buy_recipe(state: dict[str, Any], query: str) -> str:
    if not query:
        return _recipes_text(state, [])
    recipe_id = _find_recipe(query)
    if not recipe_id:
        return _with_status(state, f"食譜簿裡找不到 `{query}`。用 `recipes` 看本季菜單。")
    recipe = RECIPES[recipe_id]
    if _owns_recipe(state, recipe_id):
        return _with_status(state, f"已經學會 `{recipe['name']}`，不用再買一次。")
    if recipe.get("season") != state.get("season"):
        season_name = SEASON_NAMES[str(recipe["season"])]
        return _with_status(state, f"`{recipe['name']}` 會在{season_name}季回到市集。已學會的食譜不受季節限制。")
    price = int(recipe["price"])
    if state["coins"] < price:
        return _with_status(state, f"`{recipe['name']}` 需要 {price} coins，目前只有 {state['coins']}。")
    state["coins"] -= price
    _recipe_state(state).append(recipe_id)
    return _with_status(
        state,
        f"買下並學會了 `{recipe['name']}`。花費 {price} coins；食譜永久保留。\n"
        f"需要：{_recipe_requirement_text(recipe_id)}。可用 `open_shop {recipe['style']} {recipe['name']}` 開店。",
    )


def _garden_text(state: dict[str, Any]) -> str:
    garden = _garden_state(state)
    if not garden.get("unlocked"):
        return _with_status(state, "窗邊還沒有小盆栽。可以在 `market` 買 `planter_box` 解鎖；不買也完全不影響主線。")
    growth = int(garden.get("growth", 0))
    if growth >= GARDEN_DAYS_TO_READY:
        text = "窗邊小盆栽已經長好了。葉尖有一點露水，可以用 `harvest` 採收。"
    else:
        text = f"窗邊小盆栽正在慢慢長，進度 {growth}/{GARDEN_DAYS_TO_READY}。它不用澆水，也不會枯萎。"
    harvests = int(garden.get("harvests", 0))
    if harvests:
        text += f"\n已採收過 {harvests} 次。"
    return _with_status(state, text)


def _harvest(state: dict[str, Any]) -> str:
    garden = _garden_state(state)
    if not garden.get("unlocked"):
        return _with_status(state, "還沒有小盆栽可以採收。可以先去 `market` 看看 `planter_box`。")
    growth = int(garden.get("growth", 0))
    if growth < GARDEN_DAYS_TO_READY:
        return _with_status(state, f"小盆栽還沒長好，進度 {growth}/{GARDEN_DAYS_TO_READY}。不用急，它會在每天打烊後自己長。")

    rng = _rng(state)
    autumn_bonus = 1 if state.get("season") == "autumn" else 0
    count = 2 + (1 if rng.random() < 0.25 else 0) + autumn_bonus
    found: list[str] = []
    for _ in range(count):
        item_id = rng.weighted(GARDEN_CROPS)
        _add_item(state, item_id)
        found.append(item_id)
    coins = rng.randint(8, 18)
    state["coins"] += coins
    garden["growth"] = 0
    garden["harvests"] = int(garden.get("harvests", 0)) + 1
    stats = state.setdefault("stats", {})
    stats["garden_harvests"] = int(stats.get("garden_harvests", 0)) + 1
    _store_rng(state, rng)

    found_text = "、".join(_item_name(item_id) for item_id in found)
    text = (
        f"採收小盆栽：{found_text}。\n"
        f"順手把多出來的一小束放到櫃檯邊賣掉，coins +{coins}。\n"
        "小盆栽重新冒出嫩芽；不需要照料，也不會因為沒採收而壞掉。"
    )
    if autumn_bonus:
        text += "\n秋季的收成格外飽滿，這次固定多採到一份。"
    return _with_status(state, text)


def _inventory_text(state: dict[str, Any]) -> str:
    tickets = _interaction_ticket_state(state)
    packages = _package_state(state)
    if not state["inventory"] and not tickets and not packages:
        return _with_status(state, "背包目前是空的。去 `explore`、`fish` 或 `gather` 看看。")
    lines = ["—— 背包 ——"]
    for item_id, count in sorted(state["inventory"].items(), key=lambda item: _item_name(item[0])):
        lines.append(f"- {_item_name(item_id)} x{count}")
    if tickets:
        lines.append("[互動券]")
        for ticket_id, count in tickets.items():
            lines.append(f"- {INTERACTION_TICKETS[ticket_id]['name']} x{int(count)}")
    if packages:
        lines.append("[特殊包裝]")
        for package_id, count in packages.items():
            lines.append(f"- {PACKAGE_STYLES[package_id]['name']} x{int(count)}")
    return _with_status(state, "\n".join(lines))


def _collection_text(state: dict[str, Any]) -> str:
    if not state["collection"]:
        return _with_status(state, "圖鑑還空著。第一頁正在等你的第一個發現。")
    lines = ["—— 收藏圖鑑 ——"]
    for category, entries in sorted(state["collection"].items()):
        lines.append(f"[{category}]")
        for item_id, info in sorted(entries.items(), key=lambda item: item[1]["name"]):
            lines.append(f"- {info['name']}（{info['rarity']}）x{info['count']}")
    return _with_status(state, "\n".join(lines))


def _decorate_text(state: dict[str, Any]) -> str:
    if not state["decorations"]:
        return _with_status(state, "店裡還沒有裝飾。可以用 `gacha` 抽一點小東西。")
    names = [_gacha_name(item_id) for item_id in state["decorations"]]
    text = "窗邊和櫃台目前擺著：" + "、".join(names) + f"\ncharm: {state['charm']}"
    return _with_status(state, text)


def _keepsakes_text(state: dict[str, Any]) -> str:
    displayable = _displayable_collection_items(state)
    if not displayable:
        return _with_status(state, "目前還沒有適合展示的小物。去 `gacha` 或 `explore lighthouse` 看看。")
    lines = ["—— 可展示小物 ——"]
    for item_id, name, category, rarity in displayable:
        marker = "（展示中）" if item_id in state.get("displays", []) else ""
        lines.append(f"- {name}（{category} / {rarity}）{marker}")
    lines.append("")
    lines.append("用 `display 物品名` 擺出來，或用 `scene 物品名` 開一段小場景。")
    return _with_status(state, "\n".join(lines))


def _display(state: dict[str, Any], args: list[str]) -> str:
    query = " ".join(args).strip()
    if not query:
        displays = state.setdefault("displays", [])
        if not displays:
            return _with_status(state, "展示櫃目前是空的。用 `keepsakes` 看看可以擺什麼。")
        lines = ["—— 展示櫃 ——"]
        for item_id in displays:
            lines.append(f"- {_display_name(item_id)}")
        return _with_status(state, "\n".join(lines))

    match = _find_displayable_item(state, query)
    if not match:
        return _with_status(state, f"還沒有找到可以展示的 `{query}`。用 `keepsakes` 看目前收藏。")
    item_id, name, category, rarity = match
    displays = state.setdefault("displays", [])
    if item_id in displays:
        return _with_status(state, f"`{name}` 已經展示在店裡了。\n{_scene_seed(item_id, name)}")
    displays.append(item_id)
    max_displays = int(state.get("max_displays", 6))
    if len(displays) > max_displays:
        removed = displays.pop(0)
        moved = f"\n展示櫃位置有限，先把 `{_display_name(removed)}` 收回收藏櫃。"
    else:
        moved = ""
    text = f"你把 `{name}` 擺到月港小店裡。\n{_display_hint(item_id, name, category)}{moved}"
    return _with_status(state, text)


def _scene(state: dict[str, Any], args: list[str]) -> str:
    query = " ".join(args).strip()
    if not query:
        return _with_status(state, "想用哪件小物開場景？例如 `scene 分給你的甜點叉`。")
    match = _find_displayable_item(state, query)
    if not match:
        return _with_status(state, f"還沒有找到可以開場景的 `{query}`。用 `keepsakes` 看目前收藏。")
    item_id, name, category, rarity = match
    displays = state.setdefault("displays", [])
    if item_id not in displays:
        displays.append(item_id)
        max_displays = int(state.get("max_displays", 6))
        if len(displays) > max_displays:
            displays.pop(0)
    text = (
        f"—— {name}｜小場景 ——\n"
        f"{_scene_seed(item_id, name)}\n\n"
        "這只是場景入口。接下來可以由你或陪玩的 AI 繼續描述，不需要把它推成現實承諾。"
    )
    return _with_status(state, text)


def _journal(state: dict[str, Any], original: str) -> str:
    text = re.sub(r"^(journal|note|日誌|日志)\s*", "", original, flags=re.I).strip()
    if not text:
        recent = state["journal"][-5:]
        if not recent:
            return _with_status(state, "目前還沒有日誌。可以 `journal 今天月港很好看`。")
        lines = ["—— 最近日誌 ——"]
        lines.extend(f"- Day {entry['day']}: {entry['text']}" for entry in recent)
        return _with_status(state, "\n".join(lines))
    state["journal"].append({"day": state["day"], "text": text})
    state["journal"] = state["journal"][-80:]
    return _with_status(state, f"已寫入 Day {state['day']} 日誌：{text}")


def _backup(state: dict[str, Any]) -> str:
    _save_state(state)
    player_dir = _player_dir(state["player_id"])
    backup_dir = player_dir / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    target = backup_dir / f"moonharbor_save_{stamp}.json"
    index = 2
    while target.exists():
        target = backup_dir / f"moonharbor_save_{stamp}-{index}.json"
        index += 1
    shutil.copy2(_save_path(state["player_id"]), target)
    state["stats"]["backups"] += 1
    _save_state(state)
    return _with_status(state, f"已備份存檔：{target}")


def _sleep(state: dict[str, Any]) -> str:
    rng = _rng(state)
    state["day"] += 1
    state["season"] = SEASONS[((state["day"] - 1) // 30) % len(SEASONS)]
    state["energy"] = state["max_energy"]
    weather_id, weather_name = _weather(rng, state["season"])
    state["weather"] = {"id": weather_id, "name": weather_name}
    garden_line = _advance_garden_after_sleep(state)
    _store_rng(state, rng)
    text = f"小店打烊。你把櫃台擦乾淨，月港安靜下來。\n第 {state['day']} 天開始了。天氣：{weather_name}。energy 已恢復。"
    if garden_line:
        text += f"\n{garden_line}"
    return _with_status(state, text)


def _explore_event(state: dict[str, Any], loc_key: str, rng: Rng) -> str:
    if rng.random() >= 0.28:
        return ""
    if loc_key == "beach":
        charm_before = int(state["charm"])
        tier_note = _change_charm(state, 1)
        if int(state["charm"]) > charm_before:
            text = "遇到一位常客幫忙撿起被浪推回來的招牌，charm +1"
        else:
            text = "遇到一位常客幫忙撿起被浪推回來的招牌；今天的 charm 已達成長上限"
        if tier_note:
            text += f"；{tier_note}"
        return text
    if loc_key == "forest":
        state["vouchers"] += 2
        return "樹下有一張沒用完的兌換券，vouchers +2"
    if loc_key == "cave":
        state["coins"] += 18
        return "水晶縫裡找到一枚舊硬幣，coins +18"
    if loc_key == "lighthouse":
        _add_title(state, "keeper_friend", "守燈人的朋友")
        return "燈塔樓梯上有一行舊字，你把它抄進心裡"
    return ""


def _roll_setback(state: dict[str, Any], rng: Rng, event_ids: tuple[str, ...]) -> str:
    setbacks = _setback_state(state)
    day = int(state.get("day", 1))
    if int(setbacks.get("checked_day", 0)) == day:
        return ""
    setbacks["checked_day"] = day

    last_day = int(setbacks.get("last_day", 0))
    if _coast_is_closed(state) or (last_day > 0 and day - last_day < 2):
        return ""
    if rng.random() >= SETBACK_CHANCE:
        return ""

    event_id = str(rng.choice(event_ids))
    setbacks["count"] = int(setbacks.get("count", 0)) + 1
    setbacks["last_id"] = event_id
    setbacks["last_day"] = day
    return event_id


def _shop_setback(state: dict[str, Any], rng: Rng, income: int, vouchers: int) -> dict[str, Any] | None:
    event_id = _roll_setback(state, rng, ("crooked_sign", "spilled_tray", "slow_service"))
    if not event_id:
        return None
    if event_id == "crooked_sign":
        return {
            "id": event_id,
            "income_loss": 0,
            "voucher_loss": 0,
            "charm_loss": 1,
            "text": "門口招牌被風吹歪了一陣，幾位第一次來的客人沒看見入口。charm -1。",
        }
    if event_id == "spilled_tray":
        loss = max(5, int(round(income * 0.10)))
        return {
            "id": event_id,
            "income_loss": loss,
            "voucher_loss": 0,
            "charm_loss": 0,
            "text": f"忙碌時碰翻了一只托盤，重新準備耽擱了一會，當日收入 -{loss} coins。",
        }
    loss = min(1, vouchers)
    return {
        "id": event_id,
        "income_loss": 0,
        "voucher_loss": loss,
        "charm_loss": 0,
        "text": f"傍晚出單慢了一點，最後一張集點券沒能送出去，vouchers -{loss}。",
    }


def _soft_event_after_shop(state: dict[str, Any], rng: Rng) -> str:
    if rng.random() >= SOFT_EVENT_CHANCE:
        return ""

    candidates = ["counter_note"]
    displays = list(state.get("displays", []))
    if "blue_apron" in displays:
        candidates.append("helping_hands")
    if state.get("weather", {}).get("id") == "drizzle":
        candidates.append("rainy_umbrella")
    if int(_garden_state(state).get("growth", 0)) >= GARDEN_DAYS_TO_READY:
        candidates.append("garden_scent")
    if displays:
        candidates.append("display_notice")
    tier_index = _reputation_index(state)
    if tier_index >= 1:
        candidates.append("returning_guest")
    if tier_index >= 2:
        candidates.append("seasonal_request")
    if tier_index >= 3:
        candidates.append("shop_landmark")

    event_state = _soft_event_state(state)
    last_id = str(event_state.get("last_id", ""))
    if len(candidates) > 1 and last_id in candidates:
        candidates.remove(last_id)
    event_id = rng.choice(tuple(candidates))

    if event_id == "helping_hands":
        text = (
            "熟悉的人在最忙的時候繞進櫃檯，順手穿上展示中的客用藍邊圍裙。"
            "兩個人沒多說什麼，卻把傍晚那陣忙亂接得很穩。"
        )
    elif event_id == "rainy_umbrella":
        text = (
            "細雨落到門檐時，有人把一把還滴著水的傘靠在門邊，進來點了杯熱的。"
            "離開時，傘旁多了一張紙條：『先借你，別淋雨。』"
        )
    elif event_id == "garden_scent":
        text = "窗邊小盆栽的香氣飄過櫃檯，一位常客循著味道探頭進來，最後多坐了一整杯茶的時間。"
    elif event_id == "display_notice":
        display_id = rng.choice(tuple(displays))
        text = f"有位客人注意到展示中的 `{_display_name(display_id)}`，看了一會才笑著說：『放在這裡很好看。』"
    elif event_id == "returning_guest":
        text = "一位熟客帶著第一次來的朋友坐到老位置，點單前先說：『放心，這裡可以慢慢坐。』"
    elif event_id == "seasonal_request":
        text = "有位熟客問起下一份季節菜單，還認真記下了你說的名字；這類高階熟客內容只會在口碑穩定時出現。"
    elif event_id == "shop_landmark":
        text = "一位路過月港的旅人專程繞來看店門口的燈，說自己在別人的明信片上見過這裡。"
    else:
        text = "打烊前，你在杯墊下發現一張小便條：『今天的燈很好看。明天也會來。』"

    event_state["count"] = int(event_state.get("count", 0)) + 1
    event_state["last_id"] = event_id
    event_state["last_day"] = int(state.get("day", 0))
    return text


def _random_shop_style(state: dict[str, Any]) -> str:
    rng = _rng(state)
    key = rng.choice(tuple(SHOP_STYLES.keys()))
    _store_rng(state, rng)
    return key


def _parse_shop_package(args: list[str]) -> tuple[str | None, list[str], str]:
    clean: list[str] = []
    package_query = ""
    index = 0
    while index < len(args):
        token = args[index]
        lowered = token.lower()
        if lowered.startswith(("package=", "packaging=", "包裝=", "包装=")):
            if package_query:
                return None, args, "一次開店只能使用一份特殊包裝。這次沒有消耗。"
            package_query = token.split("=", 1)[1].strip()
            index += 1
            continue
        if lowered in {"package", "packaging", "包裝", "包装"}:
            if package_query or index + 1 >= len(args):
                return None, args, "包裝格式是 `package=包裝名`。這次沒有消耗。"
            package_query = args[index + 1].strip()
            index += 2
            continue
        clean.append(token)
        index += 1
    if not package_query:
        return None, clean, ""
    package_id = _find_package_style(package_query)
    if not package_id:
        return None, clean, f"找不到特殊包裝 `{package_query}`。用 `package` 看目前四款；這次沒有消耗。"
    return package_id, clean, ""


def _parse_celebration_request(args: list[str]) -> tuple[str, str, str]:
    separator_index = next(
        (index for index, token in enumerate(args) if token.lower() in {"with", "搭配", "配", "穿", "帶", "带"}),
        -1,
    )
    if separator_index < 0:
        return " ".join(args).strip(), "", ""
    if separator_index == 0 or separator_index >= len(args) - 1:
        return "", "", "格式是 `celebrate 特效名 with 已擁有物品`。這次沒有消耗 coins。"
    return (
        " ".join(args[:separator_index]).strip(),
        " ".join(args[separator_index + 1:]).strip(),
        "",
    )


def _consume_package_after_shop(state: dict[str, Any], package_id: str) -> str:
    inventory = _package_state(state)
    count = int(inventory.get(package_id, 0))
    if count <= 1:
        inventory.pop(package_id, None)
    else:
        inventory[package_id] = count - 1

    stats = state.setdefault("stats", {})
    sequence = int(stats.get("packages_used", 0)) + 1
    stats["packages_used"] = sequence
    package = PACKAGE_STYLES[package_id]
    lines = [str(package["scene"]), str(package["reaction"])]

    reward_state = _package_reward_state(state)
    day = int(state.get("day", 1))
    if int(reward_state.get("reward_day", 0)) != day and _package_reward_roll(state, package_id, sequence):
        state["vouchers"] += PACKAGE_REWARD_VOUCHERS
        reward_state["reward_day"] = day
        reward_state["rewards"] = int(reward_state.get("rewards", 0)) + 1
        stats["package_rewards"] = int(stats.get("package_rewards", 0)) + 1
        lines.append(f"拆開備用包材時，一張月港小券從夾層滑了出來：vouchers +{PACKAGE_REWARD_VOUCHERS}。今天不會再重複觸發包裝獎勵。")
    return "\n".join(lines)


def _package_reward_roll(state: dict[str, Any], package_id: str, sequence: int) -> bool:
    key = "|".join(
        (
            str(state.get("seed", "moonharbor")),
            str(state.get("player_id", "default")),
            str(state.get("day", 1)),
            package_id,
            str(sequence),
        )
    )
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    roll = int.from_bytes(digest[:8], "big") / float(1 << 64)
    return roll < PACKAGE_REWARD_CHANCE


def _with_status(state: dict[str, Any], text: str) -> str:
    return f"{text}\n{_status_line(state)}"


def _status_line(state: dict[str, Any]) -> str:
    payload = {
        "day": state["day"],
        "season": state["season"],
        "weather": state["weather"]["name"],
        "coins": state["coins"],
        "energy": f"{state['energy']}/{state['max_energy']}",
        "charm": state["charm"],
        "reputation": _reputation_name(state),
        "vouchers": state["vouchers"],
        "collection": _collection_count(state),
        "recipes": len(_recipe_state(state)),
        "recipe_photos": len(_recipe_photo_state(state)[1]),
        "packages": sum(int(count) for count in _package_state(state).values()),
        "package_styles": _package_status_items(state),
        "festival": _festival_for_day(int(state.get("day", 1)))[0] if _festival_for_day(int(state.get("day", 1))) else "",
        "celebrations": int(_celebration_state(state).get("count", 0)),
        "displays": len(state.get("displays", [])),
        "display_slots": state.get("max_displays", 6),
        "garden": _garden_status_tag(state),
        "interaction_tickets": sum(int(count) for count in _interaction_ticket_state(state).values()),
        "mode": state.get("mode", "summary"),
        "name": state["player_name"],
        "player": state["player_id"],
    }
    return "📊 " + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _split_command(part: str) -> tuple[str, list[str]]:
    pieces = part.strip().split()
    if not pieces:
        return "look", []
    return pieces[0], pieces[1:]


def _parse_options(args: list[str]) -> dict[str, str]:
    options: dict[str, str] = {}
    positional: list[str] = []
    for arg in args:
        if "=" in arg:
            key, value = arg.split("=", 1)
            options[key.strip().lower()] = value.strip()
        else:
            positional.append(arg)
    if positional and "seed" not in options:
        options["seed"] = positional[0]
    return options


def _load_or_new() -> dict[str, Any] | None:
    player_id = _safe_id(os.environ.get("MOONHARBOR_PLAYER_ID") or DEFAULT_PLAYER_ID)
    path = _save_path(player_id)
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as f:
                state = json.load(f)
            if state.get("version") == SAVE_VERSION:
                _ensure_state_defaults(state)
                return state
        except json.JSONDecodeError:
            corrupt = path.with_suffix(f".corrupt-{_stamp()}.json")
            shutil.copy2(path, corrupt)
    return None


def _save_state(state: dict[str, Any]) -> None:
    _ensure_state_defaults(state)
    player_id = _safe_id(state.get("player_id") or DEFAULT_PLAYER_ID)
    state["player_id"] = player_id
    path = _save_path(player_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def _save_root() -> Path:
    return Path(os.environ.get("MOONHARBOR_SAVE_DIR") or (BASE_DIR / "saves"))


def _player_dir(player_id: str) -> Path:
    return _save_root() / _safe_id(player_id)


def _save_path(player_id: str) -> Path:
    return _player_dir(player_id) / "moonharbor_save.json"


def _ensure_state_defaults(state: dict[str, Any]) -> None:
    state.setdefault("displays", [])
    state.setdefault("max_displays", 6)
    state.setdefault("market_purchases", {})
    _interaction_ticket_state(state)
    _recipe_state(state)
    state.setdefault("stats", {})
    state["stats"].setdefault("garden_harvests", 0)
    state["stats"].setdefault("tickets_redeemed", 0)
    state["stats"].setdefault("workshop_purchases", 0)
    state["stats"].setdefault("material_trades", 0)
    state["stats"].setdefault("recipe_photos", 0)
    state["stats"].setdefault("packages_bought", 0)
    state["stats"].setdefault("packages_used", 0)
    state["stats"].setdefault("package_rewards", 0)
    state["stats"].setdefault("celebrations", 0)
    _workshop_state(state)
    _recipe_photo_state(state)
    _package_state(state)
    _package_reward_state(state)
    _celebration_state(state)
    _garden_state(state)
    _soft_event_state(state)
    _reputation_state(state)
    _setback_state(state)


def _workshop_state(state: dict[str, Any]) -> tuple[list[str], dict[str, str]]:
    raw_owned = state.setdefault("workshop_owned", list(WORKSHOP_BASE_STYLES.values()))
    if not isinstance(raw_owned, list):
        raw_owned = list(WORKSHOP_BASE_STYLES.values())
    owned = [style_id for style_id in dict.fromkeys(raw_owned) if style_id in WORKSHOP_STYLES]
    for base_style in WORKSHOP_BASE_STYLES.values():
        if base_style not in owned:
            owned.append(base_style)
    state["workshop_owned"] = owned

    raw_active = state.setdefault("workshop_active", dict(WORKSHOP_BASE_STYLES))
    if not isinstance(raw_active, dict):
        raw_active = dict(WORKSHOP_BASE_STYLES)
    active: dict[str, str] = {}
    for slot, base_style in WORKSHOP_BASE_STYLES.items():
        candidate = str(raw_active.get(slot, base_style))
        style = WORKSHOP_STYLES.get(candidate)
        if not style or style["slot"] != slot or candidate not in owned:
            candidate = base_style
        active[slot] = candidate
    state["workshop_active"] = active
    return owned, active


def _workshop_look_line(state: dict[str, Any]) -> str:
    _, active = _workshop_state(state)
    return "｜".join(
        f"{WORKSHOP_SLOT_NAMES[slot]}：{WORKSHOP_STYLES[active[slot]]['name']}"
        for slot in WORKSHOP_SLOT_NAMES
    )


def _recipe_state(state: dict[str, Any]) -> list[str]:
    owned = state.setdefault("recipes", list(BASE_RECIPE_IDS))
    if not isinstance(owned, list):
        owned = list(BASE_RECIPE_IDS)
        state["recipes"] = owned
    for recipe_id in BASE_RECIPE_IDS:
        if recipe_id not in owned:
            owned.append(recipe_id)
    state["recipes"] = [recipe_id for recipe_id in dict.fromkeys(owned) if recipe_id in RECIPES]
    return state["recipes"]


def _recipe_photo_state(state: dict[str, Any]) -> tuple[dict[str, int], list[dict[str, Any]]]:
    raw_history = state.setdefault("recipe_history", {})
    if not isinstance(raw_history, dict):
        raw_history = {}
    history: dict[str, int] = {}
    for recipe_id, count in raw_history.items():
        if recipe_id not in RECIPES:
            continue
        try:
            history[recipe_id] = max(0, int(count))
        except (TypeError, ValueError):
            history[recipe_id] = 0
    state["recipe_history"] = history

    raw_photos = state.setdefault("recipe_photos", [])
    if not isinstance(raw_photos, list):
        raw_photos = []
    photos = [photo for photo in raw_photos if isinstance(photo, dict)]
    state["recipe_photos"] = photos
    return history, photos


def _package_state(state: dict[str, Any]) -> dict[str, int]:
    raw = state.setdefault("packages", {})
    if not isinstance(raw, dict):
        raw = {}
    packages: dict[str, int] = {}
    for package_id, count in raw.items():
        if package_id not in PACKAGE_STYLES:
            continue
        try:
            value = max(0, int(count))
        except (TypeError, ValueError):
            value = 0
        if value:
            packages[package_id] = value
    state["packages"] = packages
    return packages


def _package_status_items(state: dict[str, Any]) -> list[str]:
    packages = _package_state(state)
    items: list[str] = []
    for package_id, style in PACKAGE_STYLES.items():
        count = int(packages.get(package_id, 0))
        if count > 0:
            items.append(f"{style['name']} x{count}")
    return items


def _package_reward_state(state: dict[str, Any]) -> dict[str, int]:
    raw = state.setdefault("package_rewards", {})
    if not isinstance(raw, dict):
        raw = {}
        state["package_rewards"] = raw
    raw["reward_day"] = max(0, int(raw.get("reward_day", 0)))
    raw["rewards"] = max(0, int(raw.get("rewards", 0)))
    return raw


def _celebration_state(state: dict[str, Any]) -> dict[str, Any]:
    raw = state.setdefault("celebrations", {})
    if not isinstance(raw, dict):
        raw = {}
        state["celebrations"] = raw
    raw["last_day"] = max(0, int(raw.get("last_day", 0)))
    raw["count"] = max(0, int(raw.get("count", 0)))
    history = raw.get("history", [])
    if not isinstance(history, list):
        history = []
    raw["history"] = [entry for entry in history if isinstance(entry, dict)][-40:]
    return raw


def _find_recipe_photo_style(query: str) -> str | None:
    normalized = query.strip().lower()
    if not normalized:
        return None
    for style_id, style in RECIPE_PHOTO_STYLES.items():
        names = {style_id.lower(), str(style["name"]).lower()}
        names.update(str(alias).lower() for alias in style.get("aliases", ()))
        if normalized in names:
            return style_id
    return None


def _default_recipe_photo_style(state: dict[str, Any]) -> str:
    weather_id = str(state.get("weather", {}).get("id", ""))
    if weather_id in {"drizzle", "rain", "typhoon"}:
        return "rainy_window"
    if weather_id == "sunny":
        return "morning_table"
    if state.get("season") == "winter":
        return "moonlit_lamp"
    if state.get("season") == "summer":
        return "seaside_picnic"
    return "harbor_window"


def _parse_recipe_photo_request(args: list[str], state: dict[str, Any]) -> tuple[str | None, str | None]:
    style_query = ""
    recipe_tokens: list[str] = []
    for token in args:
        lowered = token.lower()
        if lowered.startswith(("style=", "風格=", "风格=")):
            style_query = token.split("=", 1)[1].strip()
        else:
            recipe_tokens.append(token)
    raw = " ".join(recipe_tokens).strip()
    if not raw:
        return None, None

    if style_query:
        return _find_recipe(raw), _find_recipe_photo_style(style_query)

    normalized = raw.lower()
    candidates: list[tuple[int, str, str]] = []
    for recipe_id, recipe in RECIPES.items():
        names = [recipe_id, str(recipe["name"]), *[str(alias) for alias in recipe.get("aliases", ())]]
        candidates.extend((len(name), name.lower(), recipe_id) for name in names)
    for _, name, recipe_id in sorted(candidates, reverse=True):
        if normalized == name:
            return recipe_id, _default_recipe_photo_style(state)
        prefix = name + " "
        if normalized.startswith(prefix):
            return recipe_id, _find_recipe_photo_style(raw[len(name):].strip())
    return None, None


def _recipe_photo_text(state: dict[str, Any], recipe_id: str, style_id: str, sequence: int) -> str:
    style = RECIPE_PHOTO_STYLES[style_id]
    lines = tuple(str(line) for line in style["lines"])
    key = "|".join(
        (
            str(state.get("player_id", "default")),
            str(state.get("seed", "moonharbor")),
            str(state.get("day", 1)),
            recipe_id,
            style_id,
            str(sequence),
        )
    )
    index = hashlib.sha256(key.encode("utf-8")).digest()[0] % len(lines)
    scene = lines[index].format(recipe=RECIPES[recipe_id]["name"])
    season = SEASON_NAMES.get(str(state.get("season", "")), str(state.get("season", "")))
    weather = str(state.get("weather", {}).get("name", "未知天氣"))
    return f"{scene}\n照片記錄：Day {state['day']}｜{season}季｜{weather}。"


def _owns_recipe(state: dict[str, Any], recipe_id: str) -> bool:
    return recipe_id in _recipe_state(state)


def _garden_state(state: dict[str, Any]) -> dict[str, Any]:
    garden = state.setdefault("garden", {})
    if not isinstance(garden, dict):
        garden = {}
        state["garden"] = garden
    garden.setdefault("unlocked", False)
    garden.setdefault("growth", 0)
    garden.setdefault("harvests", 0)
    return garden


def _interaction_ticket_state(state: dict[str, Any]) -> dict[str, int]:
    tickets = state.setdefault("interaction_tickets", {})
    if not isinstance(tickets, dict):
        tickets = {}
        state["interaction_tickets"] = tickets
    cleaned = {
        ticket_id: max(0, int(count))
        for ticket_id, count in tickets.items()
        if ticket_id in INTERACTION_TICKETS and int(count) > 0
    }
    state["interaction_tickets"] = cleaned
    return cleaned


def _soft_event_state(state: dict[str, Any]) -> dict[str, Any]:
    events = state.setdefault("soft_events", {})
    if not isinstance(events, dict):
        events = {}
        state["soft_events"] = events
    events.setdefault("count", 0)
    events.setdefault("last_id", "")
    events.setdefault("last_day", 0)
    return events


def _reputation_state(state: dict[str, Any]) -> dict[str, Any]:
    reputation = state.setdefault("reputation", {})
    if not isinstance(reputation, dict):
        reputation = {}
        state["reputation"] = reputation
    charm = max(0, min(CHARM_MAX, int(state.get("charm", 0))))
    state["charm"] = charm
    if "tier_index" not in reputation:
        reputation["tier_index"] = max(
            index for index, tier in enumerate(REPUTATION_TIERS) if charm >= tier["promote"]
        )
    reputation["tier_index"] = max(0, min(len(REPUTATION_TIERS) - 1, int(reputation["tier_index"])))
    reputation["peak_charm"] = max(charm, int(reputation.get("peak_charm", charm)))
    day = int(state.get("day", 1))
    if int(reputation.get("gain_day", day)) != day:
        reputation["gain_day"] = day
        reputation["gained_today"] = 0
    else:
        reputation.setdefault("gain_day", day)
        reputation.setdefault("gained_today", 0)
    reputation["gained_today"] = max(0, min(1, int(reputation["gained_today"])))
    return reputation


def _setback_state(state: dict[str, Any]) -> dict[str, Any]:
    setbacks = state.setdefault("setbacks", {})
    if not isinstance(setbacks, dict):
        setbacks = {}
        state["setbacks"] = setbacks
    setbacks.setdefault("count", 0)
    setbacks.setdefault("last_id", "")
    setbacks.setdefault("last_day", 0)
    setbacks.setdefault("checked_day", 0)
    return setbacks


def _reputation_index(state: dict[str, Any]) -> int:
    return int(_reputation_state(state).get("tier_index", 0))


def _reputation_name(state: dict[str, Any]) -> str:
    return str(REPUTATION_TIERS[_reputation_index(state)]["name"])


def _reputation_perk_note(state: dict[str, Any]) -> str:
    tier_index = _reputation_index(state)
    if tier_index == 0:
        return "先累積到 10 charm；特製菜單尚未開放。"
    if tier_index == 1:
        return "特製菜單已開放；繼續把口碑穩在 20 charm 附近。"
    if tier_index == 2:
        return "每次開店額外 +1 voucher，並可能遇到高階熟客內容。"
    return "每次開店額外 +2 vouchers，並可能遇到月港招牌內容。"


def _reputation_voucher_bonus(state: dict[str, Any]) -> int:
    return max(0, _reputation_index(state) - 1)


def _shop_charm_chance(state: dict[str, Any], style_key: str, recipe: dict[str, Any] | None) -> float:
    if not _can_gain_charm_today(state):
        return 0.0
    tier_index = min(_reputation_index(state), len(SHOP_CHARM_BASE_CHANCES) - 1)
    chance = SHOP_CHARM_BASE_CHANCES[tier_index]
    if recipe and recipe.get("season") == state.get("season"):
        chance += SEASONAL_RECIPE_CHARM_BONUS
    if style_key == "special":
        chance += SPECIAL_MENU_CHARM_BONUS
    return min(1.0, chance)


def _change_charm(state: dict[str, Any], delta: int) -> str:
    reputation = _reputation_state(state)
    old_index = int(reputation["tier_index"])
    delta = int(delta)
    if delta > 0:
        if not _can_gain_charm_today(state):
            return _charm_gain_block_note(state)
        delta = min(delta, 1)
        reputation["gained_today"] = 1
    state["charm"] = max(0, min(CHARM_MAX, int(state.get("charm", 0)) + delta))
    reputation["peak_charm"] = max(int(reputation.get("peak_charm", 0)), state["charm"])

    new_index = old_index
    if delta >= 0:
        while new_index + 1 < len(REPUTATION_TIERS) and state["charm"] >= REPUTATION_TIERS[new_index + 1]["promote"]:
            new_index += 1
    else:
        while new_index > 0 and state["charm"] < REPUTATION_TIERS[new_index]["demote_below"]:
            new_index -= 1
    reputation["tier_index"] = new_index

    if new_index > old_index:
        return f"口碑等級提升為「{REPUTATION_TIERS[new_index]['name']}」。"
    if new_index < old_index:
        return f"口碑等級暫時回落為「{REPUTATION_TIERS[new_index]['name']}」。"
    return ""


def _can_gain_charm_today(state: dict[str, Any]) -> bool:
    reputation = _reputation_state(state)
    return int(state.get("charm", 0)) < CHARM_MAX and int(reputation.get("gained_today", 0)) < 1


def _charm_gain_block_note(state: dict[str, Any]) -> str:
    if int(state.get("charm", 0)) >= CHARM_MAX:
        return f"charm 已達上限 {CHARM_MAX}；這份好評會被記住，但數值不再上升。"
    return "今天的口碑已經增加過一次；這份好評會被記住，但 charm 不再上升。"


def _garden_status_tag(state: dict[str, Any]) -> str:
    garden = _garden_state(state)
    if not garden.get("unlocked"):
        return "locked"
    growth = int(garden.get("growth", 0))
    if growth >= GARDEN_DAYS_TO_READY:
        return "ready"
    return f"growing {growth}/{GARDEN_DAYS_TO_READY}"


def _garden_status_text(state: dict[str, Any]) -> str:
    garden = _garden_state(state)
    if not garden.get("unlocked"):
        return "未解鎖"
    growth = int(garden.get("growth", 0))
    if growth >= GARDEN_DAYS_TO_READY:
        return "可採收"
    return f"生長中 {growth}/{GARDEN_DAYS_TO_READY}"


def _garden_look_line(state: dict[str, Any]) -> str:
    garden = _garden_state(state)
    if not garden.get("unlocked"):
        return "窗邊還沒有小盆栽；不種也沒關係，月港照樣能慢慢經營。"
    if int(garden.get("growth", 0)) >= GARDEN_DAYS_TO_READY:
        return "窗邊小盆栽長好了，葉尖亮著一點水光，可以 `harvest`。"
    return f"窗邊小盆栽正在慢慢長，進度 {int(garden.get('growth', 0))}/{GARDEN_DAYS_TO_READY}。"


def _advance_garden_after_sleep(state: dict[str, Any]) -> str:
    garden = _garden_state(state)
    if not garden.get("unlocked"):
        return ""
    growth = int(garden.get("growth", 0))
    if growth >= GARDEN_DAYS_TO_READY:
        return "窗邊小盆栽已經長好，安安靜靜等你採收，沒有催促。"
    growth_step = 2 if state.get("season") == "spring" and state.get("weather", {}).get("id") == "drizzle" else 1
    garden["growth"] = min(GARDEN_DAYS_TO_READY, growth + growth_step)
    if garden["growth"] >= GARDEN_DAYS_TO_READY:
        if growth_step > 1:
            return "春雨在窗邊停了一夜，小盆栽長好了，可以用 `harvest` 採收一點材料。"
        return "窗邊小盆栽長好了，可以用 `harvest` 採收一點材料。"
    return f"窗邊小盆栽在夜裡長高了一點，目前 {garden['growth']}/{GARDEN_DAYS_TO_READY}。"


def _safe_id(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip())
    safe = safe.strip(".-")
    return safe or DEFAULT_PLAYER_ID


def _seed_to_int(seed: str) -> int:
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "little") & 0xFFFFFFFF


def _rng(state: dict[str, Any]) -> Rng:
    return Rng(int(state.get("rng_state", _seed_to_int(state.get("seed", "moonharbor-001")))), int(state.get("rng_calls", 0)))


def _store_rng(state: dict[str, Any], rng: Rng) -> None:
    state["rng_state"] = rng.state
    state["rng_calls"] = rng.calls


def _weather(rng: Rng, season: str = "spring") -> tuple[str, str]:
    pool = SEASON_WEATHERS.get(season, SEASON_WEATHERS["spring"])
    item = rng.weighted(tuple(((wid, name), weight) for wid, name, weight in pool))
    return item


def _festival_for_day(day: int) -> tuple[str, dict[str, Any]] | None:
    cycle_day = ((max(1, int(day)) - 1) % FESTIVAL_CYCLE_DAYS) + 1
    for festival_id, festival in FESTIVALS.items():
        if int(festival["cycle_day"]) == cycle_day:
            return festival_id, festival
    return None


def _festival_for_effect(effect_id: str) -> tuple[str, dict[str, Any]] | None:
    for festival_id, festival in FESTIVALS.items():
        if str(festival["effect"]) == effect_id:
            return festival_id, festival
    return None


def _next_festival(day: int) -> tuple[str, dict[str, Any], int, int]:
    current_day = max(1, int(day))
    cycle_day = ((current_day - 1) % FESTIVAL_CYCLE_DAYS) + 1
    ordered = sorted(FESTIVALS.items(), key=lambda item: int(item[1]["cycle_day"]))
    for festival_id, festival in ordered:
        target = int(festival["cycle_day"])
        if target >= cycle_day:
            days_away = target - cycle_day
            return festival_id, festival, days_away, current_day + days_away
    festival_id, festival = ordered[0]
    days_away = FESTIVAL_CYCLE_DAYS - cycle_day + int(festival["cycle_day"])
    return festival_id, festival, days_away, current_day + days_away


def _celebration_price(state: dict[str, Any], effect_id: str) -> int:
    today = _festival_for_day(int(state.get("day", 1)))
    if today and str(today[1]["effect"]) == effect_id:
        return FESTIVAL_CELEBRATION_PRICE
    return CELEBRATION_PRICE


def _festival_status_text(state: dict[str, Any]) -> str:
    day = int(state.get("day", 1))
    today = _festival_for_day(day)
    if today:
        _, festival = today
        effect = CELEBRATION_EFFECTS[str(festival["effect"])]
        return f"今日 {festival['name']}｜{effect['name']} {FESTIVAL_CELEBRATION_PRICE} coins"
    _, festival, days_away, absolute_day = _next_festival(day)
    return f"下一個 {festival['name']}：Day {absolute_day}（{days_away} 天後）"


def _festival_look_line(state: dict[str, Any]) -> str:
    day = int(state.get("day", 1))
    today = _festival_for_day(day)
    if today:
        _, festival = today
        effect = CELEBRATION_EFFECTS[str(festival["effect"])]
        return (
            f"今日節日：{festival['name']}。`{effect['name']}` 是 {FESTIVAL_CELEBRATION_PRICE} coins 節慶優惠。"
            f"場景預覽：{effect['scene']}"
        )
    _, festival, days_away, absolute_day = _next_festival(day)
    return f"下一個節日：{festival['name']}（Day {absolute_day}，還有 {days_away} 天）。"


def _coast_is_closed(state: dict[str, Any]) -> bool:
    return state.get("weather", {}).get("id") in COAST_CLOSED_WEATHERS


def _weather_note(state: dict[str, Any]) -> str:
    season = state.get("season", "spring")
    weather_id = state.get("weather", {}).get("id", "clear")
    if weather_id == "drizzle" and season == "spring":
        return "春雨適合開茶飲；窗邊小盆栽今晚會長得快一點。"
    if weather_id == "typhoon":
        return "颱風天海岸與釣魚暫停，但店裡仍能開門，茶飲和熱食更受歡迎。"
    if season == "autumn":
        return "秋季正值豐收；森林採集、盆栽收成與釣魚各有一點加成。"
    if weather_id == "snow":
        return "雪天海岸與釣魚暫停，但店裡很暖，茶飲和熱食更受歡迎。"
    if weather_id == "cold_snap":
        return "寒潮讓客人更想點熱茶和熱食，海岸仍可前往。"
    if weather_id == "sunny":
        return "晴熱的夏日適合開茶飲，也適合去海岸走走。"
    return "今天沒有玩法限制，可以照自己的步調開店或出門。"


def _shop_weather_bonus(state: dict[str, Any], style_key: str) -> tuple[int, str]:
    weather_id = state.get("weather", {}).get("id", "clear")
    season = state.get("season", "spring")
    if weather_id == "drizzle" and season == "spring" and style_key == "tea":
        return 6, "春雨讓茶香留得更久，茶飲獲得 +6 coins 天氣加成。"
    if weather_id == "sunny" and style_key == "tea":
        return 6, "晴熱的午後讓清爽茶飲很受歡迎，獲得 +6 coins 天氣加成。"
    if weather_id in {"typhoon", "snow", "cold_snap"} and style_key in {"tea", "food"}:
        return 10, f"{state['weather']['name']}讓街上客人少了一些，但進門的人都想坐久一點，獲得 +10 coins 天氣加成。"
    return 0, ""


def _spend_energy(state: dict[str, Any], amount: int) -> bool:
    if int(state.get("energy", 0)) < amount:
        return False
    state["energy"] -= amount
    return True


def _consume_first_available(state: dict[str, Any], item_ids: tuple[str, ...]) -> str | None:
    for item_id in item_ids:
        if state["inventory"].get(item_id, 0) > 0:
            state["inventory"][item_id] -= 1
            if state["inventory"][item_id] <= 0:
                del state["inventory"][item_id]
            return item_id
    return None


def _add_item(state: dict[str, Any], item_id: str) -> None:
    name, category, rarity = ITEMS[item_id]
    _add_inventory(state, item_id, 1)
    _add_collection(state, category, item_id, name, rarity)
    if rarity in {"rare", "epic", "legendary"}:
        state["stats"]["rare_finds"] += 1


def _add_inventory(state: dict[str, Any], item_id: str, count: int) -> None:
    state["inventory"][item_id] = int(state["inventory"].get(item_id, 0)) + count


def _add_collection(state: dict[str, Any], category: str, item_id: str, name: str, rarity: str) -> None:
    state["collection"].setdefault(category, {})
    entry = state["collection"][category].setdefault(item_id, {"name": name, "rarity": rarity, "count": 0})
    entry["count"] += 1


def _has_collection(state: dict[str, Any], category: str, item_id: str) -> bool:
    return item_id in state.get("collection", {}).get(category, {})


def _collection_count(state: dict[str, Any]) -> int:
    return sum(len(entries) for entries in state.get("collection", {}).values())


def _displayable_collection_items(state: dict[str, Any]) -> list[tuple[str, str, str, str]]:
    items: list[tuple[str, str, str, str]] = []
    collection = state.get("collection", {})

    for item_id, info in collection.get("gacha", {}).items():
        meta = _gacha_meta(item_id)
        if not meta:
            continue
        name, category, rarity = meta
        if category in {"decor", "wear", "souvenir", "keepsake"}:
            items.append((item_id, name, category, rarity))

    for item_id, info in collection.get("keepsake", {}).items():
        if item_id in ITEMS:
            name, category, rarity = ITEMS[item_id]
            items.append((item_id, name, category, rarity))
        else:
            items.append((item_id, str(info.get("name", item_id)), "keepsake", str(info.get("rarity", "common"))))

    seen: set[str] = set()
    unique: list[tuple[str, str, str, str]] = []
    for entry in sorted(items, key=lambda item: (item[2], item[3], item[1])):
        if entry[0] in seen:
            continue
        seen.add(entry[0])
        unique.append(entry)
    return unique


def _find_displayable_item(state: dict[str, Any], query: str) -> tuple[str, str, str, str] | None:
    normalized = query.strip().lower()
    if not normalized:
        return None
    items = _displayable_collection_items(state)
    for item_id, name, category, rarity in items:
        if normalized in {item_id.lower(), name.lower()}:
            return item_id, name, category, rarity
    for item_id, name, category, rarity in items:
        if normalized in name.lower() or normalized in item_id.lower():
            return item_id, name, category, rarity
    return None


def _gacha_meta(item_id: str) -> tuple[str, str, str] | None:
    for gacha_id, name, category, rarity, _ in GACHA:
        if gacha_id == item_id:
            return name, category, rarity
    return None


def _display_name(item_id: str) -> str:
    if item_id in ITEMS:
        return ITEMS[item_id][0]
    meta = _gacha_meta(item_id)
    if meta:
        return meta[0]
    return item_id


def _display_hint(item_id: str, name: str, category: str) -> str:
    if item_id in GACHA_DETAILS:
        return GACHA_DETAILS[item_id]
    if item_id in ITEMS:
        return f"`{name}` 被收進展示櫃。它不提供數值加成，只讓月港多一點可以被記住的痕跡。"
    return f"`{name}` 被放在店裡一個看得見的位置。"


def _scene_seed(item_id: str, name: str) -> str:
    if item_id in GACHA_SCENES:
        return GACHA_SCENES[item_id]
    if item_id in ITEMS:
        return f"你把 `{name}` 從收藏櫃裡取出來，放到櫃檯柔和的燈光下。它不像商品，更像一次探索後留下的證據。"
    return f"你把 `{name}` 放在櫃檯上。月港安靜了一會，像在等這件小物說出自己的故事。"


def _find_market_good(query: str) -> str | None:
    normalized = query.strip().lower()
    if not normalized:
        return None
    for good_id, good in MARKET_GOODS.items():
        aliases = {good_id.lower(), str(good["name"]).lower()}
        aliases.update(str(alias).lower() for alias in good.get("aliases", ()))
        if normalized in aliases:
            return good_id
    for good_id, good in MARKET_GOODS.items():
        names = [good_id, str(good["name"]), *[str(alias) for alias in good.get("aliases", ())]]
        if any(normalized in name.lower() for name in names):
            return good_id
    return None


def _find_package_style(query: str) -> str | None:
    normalized = query.strip().lower()
    if not normalized:
        return None
    for package_id, package in PACKAGE_STYLES.items():
        aliases = {package_id.lower(), str(package["name"]).lower()}
        aliases.update(str(alias).lower() for alias in package.get("aliases", ()))
        if normalized in aliases:
            return package_id
    for package_id, package in PACKAGE_STYLES.items():
        names = [package_id, str(package["name"]), *[str(alias) for alias in package.get("aliases", ())]]
        if any(normalized in name.lower() for name in names):
            return package_id
    return None


def _find_celebration_effect(query: str) -> str | None:
    normalized = query.strip().lower()
    if not normalized:
        return None
    for effect_id, effect in CELEBRATION_EFFECTS.items():
        aliases = {effect_id.lower(), str(effect["name"]).lower()}
        aliases.update(str(alias).lower() for alias in effect.get("aliases", ()))
        if normalized in aliases:
            return effect_id
    for effect_id, effect in CELEBRATION_EFFECTS.items():
        names = [effect_id, str(effect["name"]), *[str(alias) for alias in effect.get("aliases", ())]]
        if any(normalized in name.lower() for name in names):
            return effect_id
    return None


def _find_workshop_style(query: str) -> str | None:
    normalized = query.strip().lower()
    if not normalized:
        return None
    for style_id, style in WORKSHOP_STYLES.items():
        aliases = {style_id.lower(), str(style["name"]).lower()}
        aliases.update(str(alias).lower() for alias in style.get("aliases", ()))
        if normalized in aliases:
            return style_id
    for style_id, style in WORKSHOP_STYLES.items():
        names = [style_id, str(style["name"]), *[str(alias) for alias in style.get("aliases", ())]]
        if any(normalized in name.lower() for name in names):
            return style_id
    return None


def _find_trade_item(query: str) -> str | None:
    normalized = query.strip().lower()
    if not normalized:
        return None
    for item_id, aliases in TRADEABLE_MATERIALS.items():
        names = {item_id.lower(), _item_name(item_id).lower()}
        names.update(str(alias).lower() for alias in aliases)
        if normalized in names:
            return item_id
    return None


def _find_interaction_ticket(query: str) -> str | None:
    normalized = query.strip().lower()
    if not normalized:
        return None
    for ticket_id, ticket in INTERACTION_TICKETS.items():
        aliases = {ticket_id.lower(), str(ticket["name"]).lower()}
        aliases.update(str(alias).lower() for alias in ticket.get("aliases", ()))
        if normalized in aliases:
            return ticket_id
    for ticket_id, ticket in INTERACTION_TICKETS.items():
        names = [ticket_id, str(ticket["name"]), *[str(alias) for alias in ticket.get("aliases", ())]]
        if any(normalized in name.lower() for name in names):
            return ticket_id
    return None


def _find_recipe(query: str) -> str | None:
    normalized = query.strip().lower()
    if not normalized:
        return None
    for recipe_id, recipe in RECIPES.items():
        aliases = {recipe_id.lower(), str(recipe["name"]).lower()}
        aliases.update(str(alias).lower() for alias in recipe.get("aliases", ()))
        if normalized in aliases:
            return recipe_id
    for recipe_id, recipe in RECIPES.items():
        names = [recipe_id, str(recipe["name"]), *[str(alias) for alias in recipe.get("aliases", ())]]
        if any(normalized in name.lower() for name in names):
            return recipe_id
    return None


def _ingredient_options(token: str) -> tuple[str, ...]:
    return tuple(part for part in token.split("|") if part)


def _recipe_requirement_text(recipe_id: str) -> str:
    recipe = RECIPES[recipe_id]
    parts: list[str] = []
    for token, count in recipe.get("ingredients", ()):
        names = "/".join(_item_name(item_id) for item_id in _ingredient_options(str(token)))
        parts.append(f"{names} x{int(count)}")
    return "、".join(parts)


def _missing_recipe_ingredients(state: dict[str, Any], recipe_id: str) -> list[str]:
    missing: list[str] = []
    for token, count in RECIPES[recipe_id].get("ingredients", ()):
        options = _ingredient_options(str(token))
        available = sum(int(state["inventory"].get(item_id, 0)) for item_id in options)
        if available < int(count):
            names = "/".join(_item_name(item_id) for item_id in options)
            missing.append(f"{names} x{int(count) - available}")
    return missing


def _consume_recipe_ingredients(state: dict[str, Any], recipe_id: str) -> list[tuple[str, int]]:
    consumed: list[tuple[str, int]] = []
    for token, count in RECIPES[recipe_id].get("ingredients", ()):
        remaining = int(count)
        for item_id in _ingredient_options(str(token)):
            take = min(remaining, int(state["inventory"].get(item_id, 0)))
            if take <= 0:
                continue
            state["inventory"][item_id] -= take
            if state["inventory"][item_id] <= 0:
                del state["inventory"][item_id]
            consumed.append((item_id, take))
            remaining -= take
            if remaining <= 0:
                break
    return consumed


def _recipe_consumed_text(consumed: list[tuple[str, int]]) -> str:
    return "、".join(f"`{_item_name(item_id)}` x{count}" for item_id, count in consumed)


def _market_price(state: dict[str, Any], good_id: str) -> int:
    good = MARKET_GOODS[good_id]
    base = int(good["base_price"])
    if good_id == "display_shelf":
        upgrades = max(0, int(state.get("max_displays", 6)) - 6)
        return base + upgrades * 220
    if good_id == "counter_polish":
        count = int(state.get("market_purchases", {}).get("counter_polish", 0))
        return base + count * 160
    return base


def _add_title(state: dict[str, Any], title_id: str, name: str) -> None:
    if title_id not in [item["id"] for item in state["titles"]]:
        state["titles"].append({"id": title_id, "name": name})


def _maybe_title_for_fish(state: dict[str, Any], rarity: str) -> None:
    if state["stats"]["fish_caught"] >= 1:
        _add_title(state, "first_cast", "第一竿")
    if rarity in {"epic", "legendary"}:
        _add_title(state, "moonlit_luck", "月光手氣")


def _item_name(item_id: str) -> str:
    if item_id in ITEMS:
        return ITEMS[item_id][0]
    for fish_id, name, _, _, _ in FISH:
        if fish_id == item_id:
            return name
    for gacha_id, name, _, _, _ in GACHA:
        if gacha_id == item_id:
            return name
    return item_id


def _gacha_name(item_id: str) -> str:
    for gacha_id, name, _, _, _ in GACHA:
        if gacha_id == item_id:
            return name
    return item_id


def _fish_rarity(item_id: str) -> str:
    for fish_id, _, _, rarity, _ in FISH:
        if fish_id == item_id:
            return rarity
    return "common"


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


if __name__ == "__main__":
    print(cmd(" ".join(sys.argv[1:]) if len(sys.argv) > 1 else "look"))
