from __future__ import annotations

import copy
import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class MoonharborSmokeTest(unittest.TestCase):
    def test_missing_save_requires_explicit_new_game(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            os.environ["MOONHARBOR_SAVE_DIR"] = temp
            os.environ["MOONHARBOR_PLAYER_ID"] = "fable_first_play"
            moonharbor = importlib.import_module("moonharbor")

            out = moonharbor.cmd("look")
            self.assertIn("還沒有月港小店存檔", out)
            self.assertIn("new_game name=店主名", out)
            self.assertFalse((Path(temp) / "fable_first_play" / "moonharbor_save.json").exists())

            out = moonharbor.cmd("new_game name=小克 seed=20260716 player=fable_first_play")
            self.assertIn('"name":"小克"', out)
            self.assertIn('"player":"fable_first_play"', out)

            state = moonharbor._load_or_new()
            self.assertIsNotNone(state)
            self.assertEqual(state["player_name"], "小克")
            self.assertEqual(state["player_id"], "fable_first_play")
            self.assertEqual(state["seed"], "20260716")

    def test_basic_loop_and_backup(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            os.environ["MOONHARBOR_SAVE_DIR"] = temp
            os.environ["MOONHARBOR_PLAYER_ID"] = "smoke"
            moonharbor = importlib.import_module("moonharbor")

            out = moonharbor.cmd("new_game name=測試 seed=smoke player=smoke")
            self.assertIn("月港", out)
            self.assertIn("📊", out)

            out = moonharbor.cmd("open_shop tea")
            self.assertIn("coins", out)

            out = moonharbor.cmd("explore beach; fish; gather")
            self.assertIn("📊", out)

            out = moonharbor.cmd("backup")
            self.assertIn("已備份", out)
            out = moonharbor.cmd("backup")
            self.assertIn("已備份", out)

            save_path = Path(temp) / "smoke" / "moonharbor_save.json"
            self.assertTrue(save_path.exists())
            backups = list((Path(temp) / "smoke" / "backups").glob("moonharbor_save_*.json"))
            self.assertGreaterEqual(len(backups), 2)

    def test_display_and_scene_for_gacha_keepsake(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            os.environ["MOONHARBOR_SAVE_DIR"] = temp
            os.environ["MOONHARBOR_PLAYER_ID"] = "display-smoke"
            moonharbor = importlib.import_module("moonharbor")

            moonharbor.cmd("new_game name=測試 seed=display-smoke player=display-smoke")
            state = moonharbor._load_or_new()
            state["collection"] = {
                "gacha": {
                    "shared_dessert_fork": {
                        "name": "分給你的甜點叉",
                        "rarity": "uncommon",
                        "count": 1,
                    }
                }
            }
            moonharbor._save_state(state)

            out = moonharbor.cmd("keepsakes")
            self.assertIn("分給你的甜點叉", out)

            out = moonharbor.cmd("display 分給你的甜點叉")
            self.assertIn("擺到月港小店", out)

            out = moonharbor.cmd("scene 分給你的甜點叉")
            self.assertIn("小場景", out)
            self.assertIn("最後一口", out)

            out = moonharbor.cmd("look")
            self.assertIn("分給你的甜點叉", out)

    def test_public_seasonal_gacha_items_have_display_scenes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            os.environ["MOONHARBOR_SAVE_DIR"] = temp
            os.environ["MOONHARBOR_PLAYER_ID"] = "seasonal-gacha-smoke"
            moonharbor = importlib.import_module("moonharbor")

            expected = {
                "easter_egg_basket": ("復活節彩蛋籃", "最好看的那一顆"),
                "summer_sparklers": ("夏夜手持煙火", "第一支手持煙火"),
                "pumpkin_lantern": ("南瓜提燈", "暖橘色的光"),
                "christmas_gift_sack": ("聖誕禮物袋", "包得最仔細的小禮物"),
            }
            gacha_ids = {item_id for item_id, *_ in moonharbor.GACHA}
            self.assertTrue(set(expected).issubset(gacha_ids))

            moonharbor.cmd("new_game name=測試 seed=seasonal-gacha player=seasonal-gacha-smoke")
            state = moonharbor._load_or_new()
            state["collection"] = {
                "gacha": {
                    item_id: {"name": name, "rarity": "uncommon", "count": 1}
                    for item_id, (name, _) in expected.items()
                }
            }
            moonharbor._save_state(state)

            out = moonharbor.cmd("keepsakes")
            for name, marker in expected.values():
                self.assertIn(name, out)
                scene = moonharbor.cmd(f"scene {name}")
                self.assertIn("小場景", scene)
                self.assertIn(marker, scene)

    def test_public_wear_gacha_expansion_has_display_scenes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            os.environ["MOONHARBOR_SAVE_DIR"] = temp
            os.environ["MOONHARBOR_PLAYER_ID"] = "wear-gacha-smoke"
            moonharbor = importlib.import_module("moonharbor")

            expected = {
                "moon_cufflinks": ("月亮袖扣", "最後一枚還沒有扣好", "common"),
                "little_chef_hat": ("小廚師帽", "第一份適合交給", "common"),
                "detective_short_cape": ("偵探短披風", "最後一塊甜點", "uncommon"),
                "masquerade_mask": ("假面舞會面具", "先笑出來", "uncommon"),
                "fox_tail": ("狐狸尾巴", "把得意全都說了出去", "uncommon"),
                "moonlight_cloak": ("月光斗篷", "斗篷的一側仍留著", "rare"),
                "magician_set": ("魔術師套裝", "今晚的唯一觀眾", "epic"),
                "starlit_formalwear": ("星夜禮服", "兩個人的小舞會", "legendary"),
            }
            gacha_ids = {item_id for item_id, *_ in moonharbor.GACHA}
            self.assertTrue(set(expected).issubset(gacha_ids))

            moonharbor.cmd("new_game name=測試 seed=wear-gacha player=wear-gacha-smoke")
            state = moonharbor._load_or_new()
            state["collection"] = {
                "gacha": {
                    item_id: {"name": name, "rarity": rarity, "count": 1}
                    for item_id, (name, _, rarity) in expected.items()
                }
            }
            moonharbor._save_state(state)

            out = moonharbor.cmd("keepsakes")
            for name, marker, _ in expected.values():
                self.assertIn(name, out)
                scene = moonharbor.cmd(f"scene {name}")
                self.assertIn("小場景", scene)
                self.assertIn(marker, scene)

    def test_market_buy_uses_coins(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            os.environ["MOONHARBOR_SAVE_DIR"] = temp
            os.environ["MOONHARBOR_PLAYER_ID"] = "market-smoke"
            moonharbor = importlib.import_module("moonharbor")

            moonharbor.cmd("new_game name=測試 seed=market-smoke player=market-smoke")
            state = moonharbor._load_or_new()
            state["coins"] = 1200
            state["energy"] = 4
            moonharbor._save_state(state)

            out = moonharbor.cmd("market")
            self.assertIn("月港小市集", out)
            self.assertIn("展示架擴充", out)

            out = moonharbor.cmd("buy moon_snack")
            self.assertIn("energy +1", out)
            state = moonharbor._load_or_new()
            self.assertEqual(state["energy"], 5)
            self.assertEqual(state["coins"], 1110)

            out = moonharbor.cmd("buy 展示架")
            self.assertIn("展示位增加到 7 格", out)
            state = moonharbor._load_or_new()
            self.assertEqual(state["max_displays"], 7)
            self.assertEqual(state["coins"], 630)

            out = moonharbor.cmd("buy 茶材")
            self.assertIn("暖香草", out)
            state = moonharbor._load_or_new()
            self.assertEqual(state["inventory"]["warm_herb"], 1)
            self.assertEqual(state["inventory"]["bell_leaf"], 1)

    def test_workshop_styles_are_permanent_cosmetic_and_free_to_switch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            os.environ["MOONHARBOR_SAVE_DIR"] = temp
            os.environ["MOONHARBOR_PLAYER_ID"] = "workshop-smoke"
            moonharbor = importlib.import_module("moonharbor")

            moonharbor.cmd("new_game name=測試 seed=workshop-smoke player=workshop-smoke")
            state = moonharbor._load_or_new()
            state["coins"] = 2000
            state["charm"] = 7
            state["vouchers"] = 9
            moonharbor._save_state(state)

            out = moonharbor.cmd("workshop")
            self.assertIn("月港裝潢工坊", out)
            self.assertIn("漂流木招牌框", out)

            out = moonharbor.cmd("workshop buy 漂流木招牌框")
            self.assertIn("永久外觀", out)
            self.assertIn("已立即套用，無須再輸入 `workshop use`", out)
            state = moonharbor._load_or_new()
            self.assertEqual(state["coins"], 1580)
            self.assertEqual(state["charm"], 7)
            self.assertEqual(state["vouchers"], 9)
            self.assertEqual(state["workshop_active"]["sign"], "driftwood_sign_frame")
            self.assertEqual(state["stats"]["workshop_purchases"], 1)

            out = moonharbor.cmd("workshop buy 漂流木招牌框")
            self.assertIn("已經擁有", out)
            state = moonharbor._load_or_new()
            self.assertEqual(state["coins"], 1580)
            self.assertEqual(state["stats"]["workshop_purchases"], 1)

            out = moonharbor.cmd("workshop buy 黃銅月牙招牌框")
            self.assertIn("永久外觀", out)
            state = moonharbor._load_or_new()
            self.assertEqual(state["coins"], 960)
            self.assertEqual(state["workshop_active"]["sign"], "brass_moon_sign_frame")

            out = moonharbor.cmd("workshop use 漂流木招牌框")
            self.assertIn("免費套用", out)
            state = moonharbor._load_or_new()
            self.assertEqual(state["coins"], 960)
            self.assertEqual(state["workshop_active"]["sign"], "driftwood_sign_frame")
            look = moonharbor.cmd("look")
            self.assertIn("招牌框：漂流木招牌框", look)
            self.assertIn("扭蛋／收藏裝飾 0 件", look)

    def test_material_trade_is_explicit_and_rejects_non_basic_items(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            os.environ["MOONHARBOR_SAVE_DIR"] = temp
            os.environ["MOONHARBOR_PLAYER_ID"] = "trade-smoke"
            moonharbor = importlib.import_module("moonharbor")

            moonharbor.cmd("new_game name=測試 seed=trade-smoke player=trade-smoke")
            state = moonharbor._load_or_new()
            state["coins"] = 160
            state["inventory"] = {"sweet_berry": 2, "crystal_shard": 2}
            moonharbor._save_state(state)

            before = copy.deepcopy(moonharbor._load_or_new())
            out = moonharbor.cmd("trade")
            self.assertIn("拿出同一種基礎材料 x2", out)
            after = moonharbor._load_or_new()
            self.assertEqual(after["coins"], before["coins"])
            self.assertEqual(after["inventory"], before["inventory"])

            out = moonharbor.cmd("trade 甜莓 for 暖香草")
            self.assertIn("暖香草 x1", out)
            state = moonharbor._load_or_new()
            self.assertEqual(state["coins"], 100)
            self.assertNotIn("sweet_berry", state["inventory"])
            self.assertEqual(state["inventory"]["warm_herb"], 1)
            self.assertEqual(state["stats"]["material_trades"], 1)

            before = copy.deepcopy(state)
            out = moonharbor.cmd("trade 水晶碎片 for 暖香草")
            self.assertIn("只接受暖香草", out)
            state = moonharbor._load_or_new()
            self.assertEqual(state["coins"], before["coins"])
            self.assertEqual(state["inventory"], before["inventory"])

            out = moonharbor.cmd("trade 暖香草 for 暖香草")
            self.assertIn("同一種材料", out)
            state = moonharbor._load_or_new()
            self.assertEqual(state["coins"], before["coins"])
            self.assertEqual(state["inventory"], before["inventory"])

    def test_recipe_photo_requires_cooking_and_is_purely_cosmetic(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            os.environ["MOONHARBOR_SAVE_DIR"] = temp
            os.environ["MOONHARBOR_PLAYER_ID"] = "recipe-photo-smoke"
            moonharbor = importlib.import_module("moonharbor")

            moonharbor.cmd("new_game name=測試 seed=recipe-photo-smoke player=recipe-photo-smoke")
            state = moonharbor._load_or_new()
            state["coins"] = 1000
            state["charm"] = 5
            state["vouchers"] = 8
            moonharbor._save_state(state)

            out = moonharbor.cmd("photo 月港家常茶 月港窗邊")
            self.assertIn("還沒有成功做過", out)
            self.assertEqual(moonharbor._load_or_new()["coins"], 1000)

            moonharbor.cmd("open_shop tea")
            state = moonharbor._load_or_new()
            self.assertEqual(state["recipe_history"]["house_tea"], 1)
            before = {
                "coins": state["coins"],
                "energy": state["energy"],
                "charm": state["charm"],
                "vouchers": state["vouchers"],
                "rng_state": state["rng_state"],
                "rng_calls": state["rng_calls"],
            }

            out = moonharbor.cmd("photo 月港家常茶 雨天窗景")
            self.assertIn("料理作品｜月港家常茶", out)
            self.assertIn("雨天窗景", out)
            state = moonharbor._load_or_new()
            self.assertEqual(state["coins"], before["coins"] - moonharbor.RECIPE_PHOTO_PRICE)
            for key in ("energy", "charm", "vouchers", "rng_state", "rng_calls"):
                self.assertEqual(state[key], before[key])
            self.assertEqual(len(state["recipe_photos"]), 1)
            self.assertEqual(state["recipe_photos"][0]["recipe_id"], "house_tea")
            self.assertEqual(state["recipe_photos"][0]["style_id"], "rainy_window")
            self.assertEqual(state["stats"]["recipe_photos"], 1)

            out = moonharbor.cmd("photo 月港家常茶 style=晨光木桌")
            self.assertIn("晨光木桌", out)
            self.assertEqual(len(moonharbor._load_or_new()["recipe_photos"]), 2)

            out = moonharbor.cmd("photo album")
            self.assertIn("料理作品簿｜2 張", out)
            self.assertIn("photo-0001", out)
            self.assertIn("photo-0002", out)

    def test_recipe_photo_catalog_is_data_driven(self) -> None:
        moonharbor = importlib.import_module("moonharbor")
        self.assertEqual(moonharbor.RECIPE_PHOTO_PRICE, 120)
        self.assertEqual(len(moonharbor.RECIPE_PHOTO_STYLES), 6)
        for style_id, style in moonharbor.RECIPE_PHOTO_STYLES.items():
            self.assertTrue(style["name"], style_id)
            self.assertGreaterEqual(len(style["lines"]), 2, style_id)

    def test_house_recipes_do_not_consume_undeclared_materials(self) -> None:
        moonharbor = importlib.import_module("moonharbor")
        state = moonharbor._new_state(["name=test", "seed=house-recipe", "player=house-recipe"])
        state["inventory"] = {"warm_herb": 2, "bell_leaf": 2, "sweet_berry": 2}
        before = copy.deepcopy(state["inventory"])

        original_setback = moonharbor.SETBACK_CHANCE
        original_soft = moonharbor.SOFT_EVENT_CHANCE
        moonharbor.SETBACK_CHANCE = 0.0
        moonharbor.SOFT_EVENT_CHANCE = 0.0
        try:
            out = moonharbor._open_shop(state, ["tea"])
        finally:
            moonharbor.SETBACK_CHANCE = original_setback
            moonharbor.SOFT_EVENT_CHANCE = original_soft

        self.assertEqual(state["inventory"], before)
        self.assertNotIn("用了 1 個", out)

    def test_interaction_tickets_are_repeatable_coin_sinks_and_consumables(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            os.environ["MOONHARBOR_SAVE_DIR"] = temp
            os.environ["MOONHARBOR_PLAYER_ID"] = "ticket-smoke"
            moonharbor = importlib.import_module("moonharbor")

            moonharbor.cmd("new_game name=測試 seed=ticket-smoke player=ticket-smoke")
            state = moonharbor._load_or_new()
            state["coins"] = 1000
            moonharbor._save_state(state)

            out = moonharbor.cmd("buy 摸頭券; buy 摸頭券")
            self.assertIn("目前持有 2 張", out)
            state = moonharbor._load_or_new()
            self.assertEqual(state["coins"], 640)
            self.assertEqual(state["interaction_tickets"]["headpat_ticket"], 2)

            out = moonharbor.cmd("redeem 摸頭券")
            self.assertIn("這是一份邀請", out)
            self.assertIn("剩餘 1 張", out)
            state = moonharbor._load_or_new()
            self.assertEqual(state["interaction_tickets"]["headpat_ticket"], 1)
            self.assertEqual(state["stats"]["tickets_redeemed"], 1)

            out = moonharbor.cmd("inventory")
            self.assertIn("摸頭券 x1", out)

    def test_recipe_market_purchase_and_cooking_are_safe(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            os.environ["MOONHARBOR_SAVE_DIR"] = temp
            os.environ["MOONHARBOR_PLAYER_ID"] = "recipe-smoke"
            moonharbor = importlib.import_module("moonharbor")

            moonharbor.cmd("new_game name=test seed=recipe-smoke player=recipe-smoke")
            state = moonharbor._load_or_new()
            state["day"] = 31
            state["season"] = "summer"
            state["weather"] = {"id": "sunny", "name": "晴熱"}
            state["coins"] = 1200
            state["energy"] = 6
            state["mode"] = "full"
            moonharbor._save_state(state)

            out = moonharbor.cmd("recipes")
            self.assertIn("夏日甜莓冷茶", out)
            self.assertIn("月潮海鹽烤魚", out)

            out = moonharbor.cmd("buy recipe summer_berry_iced_tea")
            self.assertIn("永久保留", out)
            state = moonharbor._load_or_new()
            self.assertEqual(state["coins"], 780)
            self.assertIn("summer_berry_iced_tea", state["recipes"])

            before_energy = state["energy"]
            out = moonharbor.cmd("open_shop tea summer_berry_iced_tea")
            self.assertIn("還缺", out)
            self.assertEqual(moonharbor._load_or_new()["energy"], before_energy)

            state = moonharbor._load_or_new()
            state["inventory"]["sweet_berry"] = 1
            state["inventory"]["bell_leaf"] = 1
            moonharbor._save_state(state)

            original_setback = moonharbor.SETBACK_CHANCE
            original_soft = moonharbor.SOFT_EVENT_CHANCE
            moonharbor.SETBACK_CHANCE = 0.0
            moonharbor.SOFT_EVENT_CHANCE = 0.0
            try:
                out = moonharbor.cmd("open_shop tea summer_berry_iced_tea")
            finally:
                moonharbor.SETBACK_CHANCE = original_setback
                moonharbor.SOFT_EVENT_CHANCE = original_soft

            self.assertIn("夏日甜莓冷茶", out)
            self.assertIn("食譜加成 +14 coins", out)
            self.assertIn("當季菜單再獲得 +10 coins", out)
            state = moonharbor._load_or_new()
            self.assertEqual(state["energy"], 4)
            self.assertNotIn("sweet_berry", state["inventory"])
            self.assertNotIn("bell_leaf", state["inventory"])

            before_coins = state["coins"]
            out = moonharbor.cmd("buy recipe rain_bell_tea")
            self.assertIn("春季回到市集", out)
            self.assertEqual(moonharbor._load_or_new()["coins"], before_coins)

    def test_old_save_migration_adds_only_free_base_recipes(self) -> None:
        moonharbor = importlib.import_module("moonharbor")
        state = moonharbor._new_state(["name=test", "seed=recipe-migration", "player=recipe-migration"])
        state.pop("recipes", None)
        state.pop("workshop_owned", None)
        state.pop("workshop_active", None)
        state.pop("recipe_history", None)
        state.pop("recipe_photos", None)

        moonharbor._ensure_state_defaults(state)

        self.assertEqual(state["recipes"], list(moonharbor.BASE_RECIPE_IDS))
        self.assertTrue(moonharbor._owns_recipe(state, "house_tea"))
        self.assertFalse(moonharbor._owns_recipe(state, "summer_berry_iced_tea"))
        self.assertEqual(state["workshop_owned"], list(moonharbor.WORKSHOP_BASE_STYLES.values()))
        self.assertEqual(state["workshop_active"], moonharbor.WORKSHOP_BASE_STYLES)
        self.assertEqual(state["recipe_history"], {})
        self.assertEqual(state["recipe_photos"], [])

    def test_recipe_catalog_is_data_driven_and_valid(self) -> None:
        moonharbor = importlib.import_module("moonharbor")
        valid_items = set(moonharbor.ITEMS)
        valid_items.update(fish_id for fish_id, *_ in moonharbor.FISH)

        self.assertEqual(len(moonharbor.RECIPES), 10)
        self.assertEqual(
            {recipe["season"] for recipe in moonharbor.RECIPES.values() if recipe["season"]},
            set(moonharbor.SEASONS),
        )
        for recipe_id, recipe in moonharbor.RECIPES.items():
            self.assertIn(recipe["style"], {"tea", "food"}, recipe_id)
            self.assertGreaterEqual(int(recipe["price"]), 0, recipe_id)
            for token, count in recipe.get("ingredients", ()):
                self.assertGreater(int(count), 0, recipe_id)
                self.assertTrue(set(token.split("|")) <= valid_items, recipe_id)

    def test_garden_unlock_growth_and_harvest(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            os.environ["MOONHARBOR_SAVE_DIR"] = temp
            os.environ["MOONHARBOR_PLAYER_ID"] = "garden-smoke"
            moonharbor = importlib.import_module("moonharbor")

            moonharbor.cmd("new_game name=測試 seed=garden-smoke player=garden-smoke")
            state = moonharbor._load_or_new()
            state["coins"] = 500
            moonharbor._save_state(state)

            out = moonharbor.cmd("market")
            self.assertIn("窗邊小盆栽", out)

            out = moonharbor.cmd("buy planter_box")
            self.assertIn("窗邊小盆栽", out)
            state = moonharbor._load_or_new()
            self.assertTrue(state["garden"]["unlocked"])
            self.assertEqual(state["coins"], 240)

            out = moonharbor.cmd("garden")
            self.assertIn("0/2", out)

            out = moonharbor.cmd("sleep")
            self.assertIn("1/2", out)

            out = moonharbor.cmd("sleep")
            self.assertIn("harvest", out)

            out = moonharbor.cmd("harvest")
            self.assertIn("採收小盆栽", out)
            state = moonharbor._load_or_new()
            self.assertEqual(state["garden"]["growth"], 0)
            self.assertEqual(state["garden"]["harvests"], 1)
            self.assertGreater(sum(state["inventory"].values()), 0)
            self.assertGreater(state["coins"], 240)

    def test_soft_events_are_flavor_only_and_do_not_repeat(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            os.environ["MOONHARBOR_SAVE_DIR"] = temp
            os.environ["MOONHARBOR_PLAYER_ID"] = "soft-event-smoke"
            moonharbor = importlib.import_module("moonharbor")

            moonharbor.cmd("new_game name=測試 seed=soft-event-smoke player=soft-event-smoke")
            state = moonharbor._load_or_new()
            state["displays"] = ["blue_apron", "shared_dessert_fork"]
            state["weather"] = {"id": "drizzle", "name": "細雨"}
            state["garden"] = {"unlocked": True, "growth": 2, "harvests": 0}
            before_resources = (state["coins"], state["vouchers"], state["charm"], state["energy"])

            original_chance = moonharbor.SOFT_EVENT_CHANCE
            moonharbor.SOFT_EVENT_CHANCE = 1.0
            try:
                rng = moonharbor.Rng(20260710)
                first = moonharbor._soft_event_after_shop(state, rng)
                first_id = state["soft_events"]["last_id"]
                second = moonharbor._soft_event_after_shop(state, rng)
                second_id = state["soft_events"]["last_id"]

                self.assertTrue(first)
                self.assertTrue(second)
                self.assertNotEqual(first_id, second_id)
                self.assertEqual(before_resources, (state["coins"], state["vouchers"], state["charm"], state["energy"]))

                moonharbor._save_state(state)
                out = moonharbor.cmd("open_shop tea")
                self.assertIn("小插曲：", out)
                state = moonharbor._load_or_new()
                self.assertEqual(state["soft_events"]["count"], 3)
            finally:
                moonharbor.SOFT_EVENT_CHANCE = original_chance

    def test_seasonal_weather_pools_and_summer_transition(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            os.environ["MOONHARBOR_SAVE_DIR"] = temp
            os.environ["MOONHARBOR_PLAYER_ID"] = "season-smoke"
            moonharbor = importlib.import_module("moonharbor")

            for season, pool in moonharbor.SEASON_WEATHERS.items():
                allowed = {weather_id for weather_id, _, _ in pool}
                seen = {
                    moonharbor._weather(moonharbor.Rng(seed), season)[0]
                    for seed in range(200)
                }
                self.assertTrue(seen)
                self.assertTrue(seen <= allowed)

            moonharbor.cmd("new_game name=測試 seed=season-smoke player=season-smoke")
            state = moonharbor._load_or_new()
            state["day"] = 30
            state["season"] = "spring"
            moonharbor._save_state(state)

            out = moonharbor.cmd("sleep")
            state = moonharbor._load_or_new()
            summer_ids = {weather_id for weather_id, _, _ in moonharbor.SEASON_WEATHERS["summer"]}
            self.assertEqual(state["day"], 31)
            self.assertEqual(state["season"], "summer")
            self.assertIn(state["weather"]["id"], summer_ids)
            self.assertIn("第 31 天", out)

    def test_severe_weather_redirects_without_spending_energy(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            os.environ["MOONHARBOR_SAVE_DIR"] = temp
            os.environ["MOONHARBOR_PLAYER_ID"] = "weather-smoke"
            moonharbor = importlib.import_module("moonharbor")

            moonharbor.cmd("new_game name=測試 seed=weather-smoke player=weather-smoke")
            state = moonharbor._load_or_new()
            state["season"] = "summer"
            state["weather"] = {"id": "typhoon", "name": "颱風"}
            state["energy"] = 6
            moonharbor._save_state(state)

            out = moonharbor.cmd("fish")
            self.assertIn("energy 沒有消耗", out)
            self.assertEqual(moonharbor._load_or_new()["energy"], 6)

            out = moonharbor.cmd("explore beach")
            self.assertIn("海岸暫時不適合", out)
            self.assertEqual(moonharbor._load_or_new()["energy"], 6)

            out = moonharbor.cmd("gather beach")
            self.assertIn("潮線附近不適合採集", out)
            self.assertEqual(moonharbor._load_or_new()["energy"], 6)

            out = moonharbor.cmd("open_shop tea")
            self.assertIn("天氣加成", out)
            self.assertEqual(moonharbor._load_or_new()["energy"], 4)

            state = moonharbor._load_or_new()
            state["season"] = "winter"
            state["weather"] = {"id": "snow", "name": "下雪"}
            state["energy"] = 4
            moonharbor._save_state(state)
            out = moonharbor.cmd("fish")
            self.assertIn("海面不適合下竿", out)
            self.assertEqual(moonharbor._load_or_new()["energy"], 4)

    def test_spring_rain_and_autumn_harvest_are_gentle_bonuses(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            os.environ["MOONHARBOR_SAVE_DIR"] = temp
            os.environ["MOONHARBOR_PLAYER_ID"] = "harvest-smoke"
            moonharbor = importlib.import_module("moonharbor")

            state = moonharbor._new_state(["name=測試", "seed=harvest-smoke", "player=harvest-smoke"])
            state["season"] = "spring"
            state["weather"] = {"id": "drizzle", "name": "細雨"}
            state["garden"] = {"unlocked": True, "growth": 0, "harvests": 0}
            line = moonharbor._advance_garden_after_sleep(state)
            self.assertEqual(state["garden"]["growth"], moonharbor.GARDEN_DAYS_TO_READY)
            self.assertIn("春雨", line)

            state["season"] = "autumn"
            state["weather"] = {"id": "harvest_breeze", "name": "涼風"}
            state["garden"]["growth"] = moonharbor.GARDEN_DAYS_TO_READY
            moonharbor._save_state(state)
            before_items = sum(state["inventory"].values())
            out = moonharbor.cmd("harvest")
            state = moonharbor._load_or_new()
            self.assertGreaterEqual(sum(state["inventory"].values()) - before_items, 3)
            self.assertIn("固定多採到一份", out)

            state["energy"] = 2
            moonharbor._save_state(state)
            before_items = sum(state["inventory"].values())
            out = moonharbor.cmd("gather forest")
            state = moonharbor._load_or_new()
            self.assertEqual(sum(state["inventory"].values()) - before_items, 2)
            self.assertIn("秋季的森林正值豐收", out)

    def test_reputation_tiers_can_fall_and_recover(self) -> None:
        moonharbor = importlib.import_module("moonharbor")
        state = moonharbor._new_state(["name=test", "seed=reputation", "player=reputation"])
        state["charm"] = 21
        state.pop("reputation", None)
        moonharbor._ensure_state_defaults(state)
        self.assertEqual(moonharbor._reputation_name(state), "月港好評店")

        note = moonharbor._change_charm(state, -4)
        self.assertEqual(state["charm"], 17)
        self.assertEqual(moonharbor._reputation_name(state), "熟客漸多")
        self.assertIn("暫時回落", note)

        note = moonharbor._change_charm(state, 3)
        self.assertEqual(state["charm"], 18)
        self.assertEqual(note, "")
        capped = moonharbor._change_charm(state, 1)
        self.assertEqual(state["charm"], 18)
        self.assertIn("今天的口碑", capped)

        state["day"] += 1
        moonharbor._change_charm(state, 1)
        self.assertEqual(state["charm"], 19)
        state["day"] += 1
        note = moonharbor._change_charm(state, 1)
        self.assertEqual(state["charm"], 20)
        self.assertEqual(moonharbor._reputation_name(state), "月港好評店")
        self.assertIn("提升", note)

        locked = moonharbor._new_state(["name=test", "seed=locked", "player=locked"])
        before_energy = locked["energy"]
        out = moonharbor._open_shop(locked, ["special"])
        self.assertIn("10 charm", out)
        self.assertEqual(locked["energy"], before_energy)

    def test_only_new_legendary_gacha_decor_can_add_daily_charm(self) -> None:
        moonharbor = importlib.import_module("moonharbor")
        original_gacha = moonharbor.GACHA
        try:
            rare = moonharbor._new_state(["name=test", "seed=rare", "player=rare"])
            rare["vouchers"] = 100
            moonharbor.GACHA = (("tiny_lighthouse", "迷你燈塔模型", "decor", "rare", 1),)
            moonharbor._gacha(rare)
            self.assertEqual(rare["charm"], 0)

            epic = moonharbor._new_state(["name=test", "seed=epic", "player=epic"])
            epic["vouchers"] = 100
            moonharbor.GACHA = (("silver_shop_bell", "銀色店鈴", "decor", "epic", 1),)
            moonharbor._gacha(epic)
            self.assertEqual(epic["charm"], 0)

            legendary = moonharbor._new_state(["name=test", "seed=legendary", "player=legendary"])
            legendary["vouchers"] = 100
            moonharbor.GACHA = (("aurora_shop_sign", "極光招牌", "decor", "legendary", 1),)
            out = moonharbor._gacha(legendary)
            self.assertEqual(legendary["charm"], 1)
            self.assertIn("charm +1", out)

            legendary["day"] += 1
            moonharbor._gacha(legendary)
            self.assertEqual(legendary["charm"], 1)
        finally:
            moonharbor.GACHA = original_gacha

    def test_counter_polish_waits_when_daily_charm_is_capped(self) -> None:
        moonharbor = importlib.import_module("moonharbor")
        state = moonharbor._new_state(["name=test", "seed=polish-cap", "player=polish-cap"])
        state["coins"] = 1000
        moonharbor._change_charm(state, 1)
        before_coins = state["coins"]

        out = moonharbor._buy(state, ["counter_polish"])

        self.assertIn("不會白花 coins", out)
        self.assertEqual(state["coins"], before_coins)

    def test_charm_has_a_hard_cap_but_can_fall_and_recover(self) -> None:
        moonharbor = importlib.import_module("moonharbor")
        state = moonharbor._new_state(["name=test", "seed=hard-cap", "player=hard-cap"])
        state["charm"] = 29
        state["day"] = 10

        moonharbor._change_charm(state, 5)
        self.assertEqual(state["charm"], moonharbor.CHARM_MAX)
        state["day"] += 1
        capped = moonharbor._change_charm(state, 1)
        self.assertEqual(state["charm"], moonharbor.CHARM_MAX)
        self.assertIn("已達上限", capped)

        moonharbor._change_charm(state, -1)
        self.assertEqual(state["charm"], moonharbor.CHARM_MAX - 1)
        state["day"] += 1
        moonharbor._change_charm(state, 1)
        self.assertEqual(state["charm"], moonharbor.CHARM_MAX)

        old_state = moonharbor._new_state(["name=test", "seed=old-cap", "player=old-cap"])
        old_state["charm"] = 87
        moonharbor._ensure_state_defaults(old_state)
        self.assertEqual(old_state["charm"], moonharbor.CHARM_MAX)

    def test_shop_charm_chance_slows_across_reputation_tiers(self) -> None:
        moonharbor = importlib.import_module("moonharbor")
        state = moonharbor._new_state(["name=test", "seed=charm-curve", "player=charm-curve"])

        self.assertAlmostEqual(moonharbor._shop_charm_chance(state, "tea", moonharbor.RECIPES["house_tea"]), 0.25)
        self.assertAlmostEqual(moonharbor._shop_charm_chance(state, "tea", moonharbor.RECIPES["rain_bell_tea"]), 0.30)

        state["charm"] = 10
        state["reputation"]["tier_index"] = 1
        self.assertAlmostEqual(moonharbor._shop_charm_chance(state, "tea", moonharbor.RECIPES["house_tea"]), 0.18)
        self.assertAlmostEqual(moonharbor._shop_charm_chance(state, "tea", moonharbor.RECIPES["rain_bell_tea"]), 0.23)
        self.assertAlmostEqual(moonharbor._shop_charm_chance(state, "special", None), 0.26)

        state["charm"] = 20
        state["reputation"]["tier_index"] = 2
        self.assertAlmostEqual(moonharbor._shop_charm_chance(state, "tea", moonharbor.RECIPES["house_tea"]), 0.10)
        self.assertAlmostEqual(moonharbor._shop_charm_chance(state, "tea", moonharbor.RECIPES["rain_bell_tea"]), 0.15)
        self.assertAlmostEqual(moonharbor._shop_charm_chance(state, "special", None), 0.18)

        moonharbor._change_charm(state, 1)
        self.assertEqual(moonharbor._shop_charm_chance(state, "special", None), 0.0)

    def test_charm_income_bonus_stops_growing_after_twenty(self) -> None:
        moonharbor = importlib.import_module("moonharbor")
        base_state = moonharbor._new_state(["name=test", "seed=income-cap", "player=income-cap"])
        low = copy.deepcopy(base_state)
        high = copy.deepcopy(base_state)
        low["charm"] = 20
        high["charm"] = 80

        original_setback = moonharbor.SETBACK_CHANCE
        original_soft = moonharbor.SOFT_EVENT_CHANCE
        moonharbor.SETBACK_CHANCE = 0.0
        moonharbor.SOFT_EVENT_CHANCE = 0.0
        try:
            low_before = low["coins"]
            high_before = high["coins"]
            moonharbor._open_shop(low, ["tea"])
            moonharbor._open_shop(high, ["tea"])
            self.assertEqual(low["coins"] - low_before, high["coins"] - high_before)
        finally:
            moonharbor.SETBACK_CHANCE = original_setback
            moonharbor.SOFT_EVENT_CHANCE = original_soft

    def test_shop_setback_can_lower_charm_and_active_tier(self) -> None:
        moonharbor = importlib.import_module("moonharbor")
        state = moonharbor._new_state(["name=test", "seed=shop-setback", "player=shop-setback"])
        state["charm"] = 18
        state["reputation"] = {"tier_index": 2, "peak_charm": 21}
        state["mode"] = "full"

        original_shop_setback = moonharbor._shop_setback
        moonharbor._shop_setback = lambda *_: {
            "id": "crooked_sign",
            "income_loss": 0,
            "voucher_loss": 0,
            "charm_loss": 1,
            "text": "測試用招牌事件。charm -1。",
        }
        try:
            out = moonharbor._open_shop(state, ["tea"])
            self.assertEqual(state["charm"], 17)
            self.assertEqual(moonharbor._reputation_name(state), "熟客漸多")
            self.assertIn("charm -1", out)
            self.assertIn("暫時回落", out)
        finally:
            moonharbor._shop_setback = original_shop_setback

    def test_setback_rolls_once_per_day_with_cooldown(self) -> None:
        moonharbor = importlib.import_module("moonharbor")
        state = moonharbor._new_state(["name=test", "seed=setback-roll", "player=setback-roll"])
        state["day"] = 5
        state["weather"] = {"id": "clear", "name": "晴"}

        original_chance = moonharbor.SETBACK_CHANCE
        moonharbor.SETBACK_CHANCE = 1.0
        try:
            first = moonharbor._roll_setback(state, moonharbor.Rng(1), ("first",))
            second = moonharbor._roll_setback(state, moonharbor.Rng(2), ("second",))
            self.assertEqual(first, "first")
            self.assertEqual(second, "")

            state["day"] = 6
            cooldown = moonharbor._roll_setback(state, moonharbor.Rng(3), ("cooldown",))
            self.assertEqual(cooldown, "")

            state["day"] = 7
            next_event = moonharbor._roll_setback(state, moonharbor.Rng(4), ("next",))
            self.assertEqual(next_event, "next")
        finally:
            moonharbor.SETBACK_CHANCE = original_chance

    def test_outdoor_setbacks_reduce_only_the_current_reward(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            os.environ["MOONHARBOR_SAVE_DIR"] = temp
            os.environ["MOONHARBOR_PLAYER_ID"] = "outdoor-setback"
            moonharbor = importlib.import_module("moonharbor")
            moonharbor.cmd("new_game name=test seed=outdoor-setback player=outdoor-setback")

            state = moonharbor._load_or_new()
            state["day"] = 5
            state["weather"] = {"id": "clear", "name": "晴"}
            state["energy"] = 6
            state["mode"] = "full"
            moonharbor._save_state(state)

            original_chance = moonharbor.SETBACK_CHANCE
            moonharbor.SETBACK_CHANCE = 1.0
            try:
                before_items = sum(state["inventory"].values())
                out = moonharbor.cmd("fish")
                state = moonharbor._load_or_new()
                self.assertIn("空手收竿", out)
                self.assertEqual(state["energy"], 5)
                self.assertEqual(sum(state["inventory"].values()), before_items)

                state["day"] = 7
                state["energy"] = 6
                moonharbor._save_state(state)
                before_items = sum(state["inventory"].values())
                out = moonharbor.cmd("explore forest")
                state = moonharbor._load_or_new()
                self.assertIn("只帶回一份材料", out)
                self.assertEqual(sum(state["inventory"].values()) - before_items, 1)
            finally:
                moonharbor.SETBACK_CHANCE = original_chance

    def test_package_catalog_purchase_and_success_only_consumption(self) -> None:
        moonharbor = importlib.import_module("moonharbor")
        state = moonharbor._new_state(["name=test", "seed=package-safe", "player=package-safe"])
        state["coins"] = 1000

        out = moonharbor._package(state, ["buy", "月紋緞帶"])
        self.assertIn("月紋緞帶", out)
        self.assertEqual(state["coins"], 1000 - moonharbor.PACKAGE_PRICE)
        self.assertEqual(state["packages"]["moon_ribbon"], 1)
        self.assertIn("特殊包裝：1（月紋緞帶 x1）", moonharbor._status_text(state))
        self.assertIn('"packages":1', moonharbor._status_line(state))
        self.assertIn('"package_styles":["月紋緞帶 x1"]', moonharbor._status_line(state))

        state["energy"] = 0
        before_inventory = copy.deepcopy(state["inventory"])
        out = moonharbor._open_shop(state, ["tea", "package=月紋緞帶"])
        self.assertIn("energy 不夠", out)
        self.assertEqual(state["packages"]["moon_ribbon"], 1)
        self.assertEqual(state["inventory"], before_inventory)

        state["energy"] = 6
        packaged = copy.deepcopy(state)
        plain = copy.deepcopy(state)
        plain["packages"] = {}
        original_reward_chance = moonharbor.PACKAGE_REWARD_CHANCE
        original_setback = moonharbor.SETBACK_CHANCE
        original_soft = moonharbor.SOFT_EVENT_CHANCE
        moonharbor.PACKAGE_REWARD_CHANCE = 0.0
        moonharbor.SETBACK_CHANCE = 0.0
        moonharbor.SOFT_EVENT_CHANCE = 0.0
        try:
            packaged_out = moonharbor._open_shop(packaged, ["tea", "package=月紋緞帶"])
            moonharbor._open_shop(plain, ["tea"])
        finally:
            moonharbor.PACKAGE_REWARD_CHANCE = original_reward_chance
            moonharbor.SETBACK_CHANCE = original_setback
            moonharbor.SOFT_EVENT_CHANCE = original_soft

        self.assertIn("特殊包裝", packaged_out)
        self.assertNotIn("moon_ribbon", packaged["packages"])
        self.assertEqual(packaged["rng_state"], plain["rng_state"])
        self.assertEqual(packaged["rng_calls"], plain["rng_calls"])
        self.assertEqual(packaged["coins"], plain["coins"])
        self.assertEqual(packaged["charm"], plain["charm"])

    def test_package_reward_is_independent_and_limited_to_once_per_day(self) -> None:
        moonharbor = importlib.import_module("moonharbor")
        state = moonharbor._new_state(["name=test", "seed=package-reward", "player=package-reward"])
        state["packages"] = {"sea_blue_box": 2}
        state["energy"] = 6
        original_reward_chance = moonharbor.PACKAGE_REWARD_CHANCE
        original_setback = moonharbor.SETBACK_CHANCE
        original_soft = moonharbor.SOFT_EVENT_CHANCE
        moonharbor.PACKAGE_REWARD_CHANCE = 1.0
        moonharbor.SETBACK_CHANCE = 0.0
        moonharbor.SOFT_EVENT_CHANCE = 0.0
        try:
            first = moonharbor._open_shop(state, ["tea", "package=海藍紙盒"])
            second = moonharbor._open_shop(state, ["food", "package=海藍紙盒"])
        finally:
            moonharbor.PACKAGE_REWARD_CHANCE = original_reward_chance
            moonharbor.SETBACK_CHANCE = original_setback
            moonharbor.SOFT_EVENT_CHANCE = original_soft

        self.assertIn(f"vouchers +{moonharbor.PACKAGE_REWARD_VOUCHERS}", first)
        self.assertNotIn("從夾層滑了出來", second)
        self.assertEqual(state["stats"]["packages_used"], 2)
        self.assertEqual(state["stats"]["package_rewards"], 1)
        self.assertEqual(state["package_rewards"]["reward_day"], state["day"])

    def test_festivals_repeat_and_matching_celebration_is_discounted(self) -> None:
        moonharbor = importlib.import_module("moonharbor")
        first = moonharbor._festival_for_day(15)
        repeated = moonharbor._festival_for_day(135)
        self.assertIsNotNone(first)
        self.assertIsNotNone(repeated)
        self.assertEqual(first[0], "egg_market")
        self.assertEqual(repeated[0], "egg_market")
        self.assertIsNone(moonharbor._festival_for_day(16))

        festival_state = moonharbor._new_state(["name=test", "seed=festival", "player=festival"])
        festival_state["day"] = 15
        festival_state["coins"] = 1000
        self.assertIn("場景預覽", moonharbor._festival_text(festival_state))
        self.assertIn("適合笑著穿過去的春天", moonharbor._festival_look_line(festival_state))
        self.assertIn("今日場景預覽", moonharbor._celebrate(festival_state, []))
        before_rng = (festival_state["rng_state"], festival_state["rng_calls"])
        before_resources = (festival_state["energy"], festival_state["charm"], festival_state["vouchers"])
        out = moonharbor._celebrate(festival_state, ["彩蛋紙花雨"])
        self.assertIn("彩蛋花市", out)
        self.assertEqual(festival_state["coins"], 1000 - moonharbor.FESTIVAL_CELEBRATION_PRICE)
        self.assertEqual((festival_state["rng_state"], festival_state["rng_calls"]), before_rng)
        self.assertEqual((festival_state["energy"], festival_state["charm"], festival_state["vouchers"]), before_resources)

        before_second = festival_state["coins"]
        second = moonharbor._celebrate(festival_state, ["海港煙火"])
        self.assertIn("今天已經舉辦過", second)
        self.assertEqual(festival_state["coins"], before_second)

        ordinary = moonharbor._new_state(["name=test", "seed=ordinary", "player=ordinary"])
        ordinary["day"] = 16
        ordinary["coins"] = 1000
        moonharbor._celebrate(ordinary, ["彩蛋紙花雨"])
        self.assertEqual(ordinary["coins"], 1000 - moonharbor.CELEBRATION_PRICE)

    def test_celebration_prop_must_be_owned_and_is_never_consumed(self) -> None:
        moonharbor = importlib.import_module("moonharbor")
        state = moonharbor._new_state(["name=test", "seed=festival-prop", "player=festival-prop"])
        state["day"] = 45
        state["coins"] = 1000
        state["collection"] = {
            "gacha": {
                "summer_sparklers": {
                    "name": "夏夜手持煙火",
                    "rarity": "uncommon",
                    "count": 1,
                }
            }
        }
        before_collection = copy.deepcopy(state["collection"])
        out = moonharbor._celebrate(state, ["海港煙火", "with", "夏夜手持煙火"])
        self.assertIn("第一支手持煙火", out)
        self.assertIn("沒有被消耗", out)
        self.assertEqual(state["collection"], before_collection)
        self.assertEqual(state["coins"], 1000 - moonharbor.FESTIVAL_CELEBRATION_PRICE)

        missing = moonharbor._new_state(["name=test", "seed=missing-prop", "player=missing-prop"])
        missing["day"] = 45
        missing["coins"] = 1000
        rejected = moonharbor._celebrate(missing, ["海港煙火", "with", "夏夜手持煙火"])
        self.assertIn("收藏裡找不到", rejected)
        self.assertEqual(missing["coins"], 1000)

    def test_celebration_reports_owned_but_incompatible_keepsake(self) -> None:
        moonharbor = importlib.import_module("moonharbor")
        state = moonharbor._new_state(["name=test", "seed=festival-keepsake", "player=festival-keepsake"])
        state["day"] = 45
        state["coins"] = 1000
        state["collection"] = {
            "gacha": {},
            "keepsake": {
                "brass_key": {
                    "name": "黃銅小鑰匙",
                    "rarity": "rare",
                    "count": 1,
                }
            },
        }

        out = moonharbor._celebrate(state, ["海港煙火", "with", "黃銅小鑰匙"])

        self.assertIn("不屬於可穿戴物", out)
        self.assertNotIn("收藏裡找不到", out)
        self.assertEqual(state["coins"], 1000)


if __name__ == "__main__":
    unittest.main()
