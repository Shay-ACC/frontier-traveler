import asyncio
import sys
from app.engine.game_engine import GameEngine


async def main():
    engine = GameEngine()

    print("=" * 60)
    print("  《边境小镇：记忆旅人》")
    print("  Border Town: Memory Traveler")
    print("=" * 60)
    print()
    print("可用命令：")
    print("  /start      - 开始新游戏")
    print("  /state      - 查看当前状态")
    print("  /help       - 显示帮助")
    print("  /quit       - 退出游戏")
    print()

    game_id = None

    while True:
        try:
            user_input = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见，旅行者。")
            break

        if not user_input:
            continue

        if user_input == "/quit":
            print("再见，旅行者。")
            break
        elif user_input == "/help":
            print("\n可用命令：")
            print("  /start      - 开始新游戏")
            print("  /state      - 查看当前状态")
            print("  /help       - 显示帮助")
            print("  /quit       - 退出游戏")
            print("\n游戏提示：")
            print("  - 使用自然语言与 NPC 交谈")
            print("  - 输入「前往XX」来移动到其他地点")
            print("  - 输入「和XX交谈」来与 NPC 对话")
            continue
        elif user_input == "/start":
            result = await engine.start_game()
            game_id = result.game_id
            print(f"\n{'─' * 50}")
            print(result.opening_narrative)
            print(f"{'─' * 50}")
            print(f"\n当前位置：{result.current_location.name}")
            for npc in result.available_npcs:
                print(f"  - {npc.name}（{npc.role}）")
            print(f"\n可用操作：")
            for action in ["和" + npc.name + "交谈" for npc in result.available_npcs]:
                print(f"  - {action}")
            for loc_id in ["town_hall"]:
                loc = engine.world_state.get_location(loc_id)
                if loc:
                    print(f"  - 前往{loc.name}")
            continue
        elif user_input == "/state":
            if not game_id:
                print("请先使用 /start 开始游戏。")
                continue
            state = await engine.get_state(game_id)
            if state is None:
                print("游戏会话不存在。")
                game_id = None
                continue

            loc = engine.world_state.get_location(state.world_state.current_location)
            loc_name = loc.name if loc else state.world_state.current_location

            print(f"\n{'═' * 50}")
            print(f"  游戏状态")
            print(f"{'═' * 50}")
            print(f"  当前位置：{loc_name}")
            print(f"  时间：{state.world_state.time_of_day}")
            print(f"  回合数：{state.world_state.turn_count}")
            print(f"\n  关系：")
            for rel in state.relationships:
                npc = engine.npc_agent.get_npc(rel.npc_id)
                npc_name = npc.name if npc else rel.npc_id
                print(f"    {npc_name} - 信任:{rel.trust} 好感:{rel.affection} [{rel.status}]")
            print(f"\n  任务：")
            for qs in state.quest_states:
                quest = engine.quest_manager.get_quest(qs.quest_id)
                quest_title = quest.title if quest else qs.quest_id
                status = "✓ 已完成" if qs.completed else f"阶段: {qs.current_stage}"
                print(f"    [{quest.type.upper()}] {quest_title} - {status}")
            print(f"{'═' * 50}")
            continue

        if not game_id:
            print("请先使用 /start 开始游戏。")
            continue

        result = await engine.process_input(game_id, user_input)

        if result.npc_response == "游戏会话不存在。":
            print("游戏会话已失效，请使用 /start 开始新游戏。")
            game_id = None
            continue

        print()
        if result.narration:
            print(f"[旁白] {result.narration}")
            print()

        if result.npc_response:
            npc = engine.npc_agent.get_npc(result.npc_id) if result.npc_id else None
            npc_name = npc.name if npc else "???"
            print(f"{npc_name}：{result.npc_response}")
            print()

        if result.state_changes.quest_updates:
            for qu in result.state_changes.quest_updates:
                quest = engine.quest_manager.get_quest(qu.quest_id)
                quest_title = quest.title if quest else qu.quest_id
                print(f"  [任务更新] {quest_title}: {qu.old_stage} → {qu.new_stage}")

        if result.state_changes.relationship_changes:
            for rc in result.state_changes.relationship_changes:
                npc = engine.npc_agent.get_npc(rc.npc_id)
                npc_name = npc.name if npc else rc.npc_id
                direction = "↑" if rc.delta > 0 else "↓"
                print(f"  [关系变化] {npc_name} {rc.field} {direction}{abs(rc.delta)}")

        if result.state_changes.flag_changes:
            for flag, value in result.state_changes.flag_changes.items():
                print(f"  [事件] {flag}: {value}")

        if result.available_actions:
            print(f"\n可用操作：{', '.join(result.available_actions)}")


if __name__ == "__main__":
    asyncio.run(main())
