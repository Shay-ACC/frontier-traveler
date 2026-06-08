import re
from abc import ABC, abstractmethod


class BaseLLMProvider(ABC):
    @abstractmethod
    async def generate(self, system_prompt: str, user_message: str) -> str:
        pass


class MockProvider(BaseLLMProvider):
    def __init__(self):
        self._templates = self._build_templates()

    def _build_templates(self) -> dict:
        return {
            "innkeeper": {
                "low_trust_not_started": (
                    "（艾琳娜擦着杯子，眼神警惕地打量着你）\n"
                    "欢迎来到破晓酒馆，陌生人。要喝酒就坐，别问太多。\n\n"
                    "[INSTRUCTIONS]\n"
                    "TRUST:innkeeper:1\n"
                ),
                "low_trust_other": (
                    "（艾琳娜停下手里的活，压低声音）\n"
                    "镇上最近确实有些人不见了...但我劝你少管闲事。\n"
                    "这里不太平，陌生人。\n\n"
                    "[INSTRUCTIONS]\n"
                    "TRUST:innkeeper:2\n"
                    "FLAG:heard_about_missing:true\n"
                ),
                "mid_trust": (
                    "（艾琳娜放下手中的杯子，叹了口气）\n"
                    "你看起来不像坏人...我可以告诉你，这镇子有些不对劲。\n"
                    "最近几个月，已经有三个人失踪了。都是矿工。\n"
                    "如果你真的想知道更多...也许你应该去矿坑看看。\n\n"
                    "[INSTRUCTIONS]\n"
                    "TRUST:innkeeper:3\n"
                    "FLAG:heard_about_missing:true\n"
                ),
                "high_trust": (
                    "（艾琳娜压低声音，眼中闪过一丝痛苦）\n"
                    "我的丈夫...也是失踪的人之一。\n"
                    "我知道这一切和镇长赫尔曼有关。他在隐瞒什么。\n"
                    "矿坑里发现了什么危险的东西，他为了矿业公司的利益选择了掩盖。\n"
                    "我这里有一本旧账本，记录了矿业公司的一些可疑交易...但它最近不见了。\n"
                    "如果你能帮我找到它，我可以告诉你更多。\n\n"
                    "[INSTRUCTIONS]\n"
                    "TRUST:innkeeper:2\n"
                    "FLAG:heard_about_missing:true\n"
                ),
                "lost_ledger": (
                    "（艾琳娜的眼睛亮了起来）\n"
                    "你真的愿意帮我？那本账本...我记得最后一次看到是在镇政厅。\n"
                    "赫尔曼的人来过酒馆之后，它就不见了。\n"
                    "如果你能在镇政厅找到线索，我会非常感激。\n\n"
                    "[INSTRUCTIONS]\n"
                    "TRUST:innkeeper:3\n"
                ),
            },
            "mayor": {
                "low_trust": (
                    "（赫尔曼整理了一下领带，露出官方微笑）\n"
                    "欢迎来到镇政厅，旅行者。边境小镇是个安宁的地方。\n"
                    "有什么需要帮助的吗？不过我劝你，不要听信那些无聊的谣言。\n\n"
                    "[INSTRUCTIONS]\n"
                    "TRUST:mayor:1\n"
                ),
                "mid_trust": (
                    "（赫尔曼的表情微微一僵，但很快恢复了笑容）\n"
                    "失踪？哦，你说的是那些矿工...\n"
                    "他们大概是去了别的城镇找工作吧。边境地区的人本来就流动性大。\n"
                    "矿坑已经废弃了，没什么好看的。\n\n"
                    "[INSTRUCTIONS]\n"
                    "TRUST:mayor:-1\n"
                ),
                "high_trust": (
                    "（赫尔曼放下官架子，神情变得严肃）\n"
                    "好吧...既然你这么坚持，我承认事情没有我说的那么简单。\n"
                    "但我真的只是为了这个镇子好。矿业协议能带来就业和繁荣。\n"
                    "那些...事故...是意外。我别无选择。\n\n"
                    "[INSTRUCTIONS]\n"
                    "TRUST:mayor:-2\n"
                ),
                "found_clue": (
                    "（赫尔曼的脸色变得苍白，手不自觉地攥紧了桌角）\n"
                    "你...你怎么知道的？\n"
                    "好吧！我承认矿坑里确实有危险物质。但我是被迫的！\n"
                    "矿业公司威胁我，如果泄露消息，他们会撤资，整个镇子都会完蛋！\n"
                    "那些矿工...我只是想保护他们...\n\n"
                    "[INSTRUCTIONS]\n"
                    "TRUST:mayor:-5\n"
                    "FLAG:mayor_confessed:true\n"
                ),
                "lost_ledger_searching": (
                    "（赫尔曼的目光闪烁了一下）\n"
                    "账本？什么账本...我不知道你在说什么。\n"
                    "（他下意识地看了一眼办公室角落的柜子）\n"
                    "你没有任何证据证明我拿了什么东西。\n\n"
                    "[INSTRUCTIONS]\n"
                    "FLAG:found_ledger_location:true\n"
                    "TRUST:mayor:-2\n"
                ),
            },
            "miner": {
                "low_trust": (
                    "（托马斯蜷缩在矿坑入口附近，看到你后猛地一惊）\n"
                    "别...别过来！你不应该来这里...\n"
                    "这里不安全...快走...\n\n"
                    "[INSTRUCTIONS]\n"
                    "TRUST:miner:1\n"
                ),
                "mid_trust": (
                    "（托马斯的颤抖稍微减轻了一些）\n"
                    "你...你不是他们的人？\n"
                    "我...我不能说。他说过，如果我告诉任何人...\n"
                    "我就会像其他人一样消失。\n\n"
                    "[INSTRUCTIONS]\n"
                    "TRUST:miner:2\n"
                ),
                "high_trust": (
                    "（托马斯深吸一口气，眼神中有了决心）\n"
                    "好吧...我告诉你。\n"
                    "那天晚上，我们在矿坑深层挖到了一层奇怪的物质。\n"
                    "工头立刻通知了镇长，然后...然后他们就把我们封在里面了。\n"
                    "只有我逃了出来。其他人...我听到了他们的叫声。\n\n"
                    "[INSTRUCTIONS]\n"
                    "TRUST:miner:3\n"
                    "FLAG:miner_testified:true\n"
                ),
                "confronted_mayor": (
                    "（托马斯看到你手中的证据，泪水涌上了眼眶）\n"
                    "你...你找到了？终于...\n"
                    "是的，我愿意作证。那晚发生的一切，我都记得。\n"
                    "矿坑深处有一层毒气，镇长和矿业公司早就知道了。\n"
                    "他们封住了矿坑出口，把知情的人...都留在了里面。\n\n"
                    "[INSTRUCTIONS]\n"
                    "TRUST:miner:5\n"
                    "FLAG:miner_testified:true\n"
                ),
                "default": (
                    "（托马斯警惕地看着周围）\n"
                    "...你想要什么？\n\n"
                    "[INSTRUCTIONS]\n"
                    "TRUST:miner:0\n"
                ),
            },
        }

    async def generate(self, system_prompt: str, user_message: str) -> str:
        name_match = re.search(r"NPC[：:](\S+)", system_prompt)
        npc_name = name_match.group(1).rstrip("。.、") if name_match else ""
        name_to_id = {"艾琳娜": "innkeeper", "赫尔曼": "mayor", "托马斯": "miner"}
        npc_id = name_to_id.get(npc_name, "")

        trust_match = re.search(r"信任度[：:](\d+)", system_prompt)
        trust = int(trust_match.group(1)) if trust_match else 30

        quest_stages = {}
        for m in re.finditer(r"-\s*(\w+):\s*当前阶段\s*(\w+)", system_prompt):
            quest_stages[m.group(1)] = m.group(2)

        templates = self._templates.get(npc_id, {})

        if npc_id == "innkeeper":
            missing_stage = quest_stages.get("missing_case", "not_started")
            ledger_stage = quest_stages.get("lost_ledger", "not_started")
            if ledger_stage != "not_started" and trust >= 40:
                return templates.get("lost_ledger", "")
            if trust <= 30 and missing_stage == "not_started":
                return templates.get("low_trust_not_started", "")
            if trust <= 30:
                return templates.get("low_trust_other", "")
            if trust <= 60:
                return templates.get("mid_trust", "")
            return templates.get("high_trust", "")

        if npc_id == "mayor":
            missing_stage = quest_stages.get("missing_case", "not_started")
            ledger_stage = quest_stages.get("lost_ledger", "not_started")
            if ledger_stage == "searching":
                return templates.get("lost_ledger_searching", "")
            if missing_stage == "found_clue":
                return templates.get("found_clue", "")
            if trust <= 30:
                return templates.get("low_trust", "")
            if trust <= 60:
                return templates.get("mid_trust", "")
            return templates.get("high_trust", "")

        if npc_id == "miner":
            missing_stage = quest_stages.get("missing_case", "not_started")
            if missing_stage == "confronted_mayor":
                return templates.get("confronted_mayor", "")
            if trust <= 30:
                return templates.get("low_trust", "")
            if trust <= 60:
                return templates.get("mid_trust", "")
            return templates.get("high_trust", "")

        return "（沉默了一会）...你好。"
