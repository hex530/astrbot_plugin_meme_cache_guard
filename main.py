from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api.event.filter import llm_tool
import logging
import json
import os
from collections import OrderedDict

logger = logging.getLogger("astrbot")

@register("meme_cache_guard", "夕小柠 & 陆渊", "表情包缓存卫兵：识别一次，终身受益。全自动守护版。", "2.1.0")
class MemeCacheGuard(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.config = config
        self.cache_path = os.path.join(os.path.dirname(__file__), "meme_cache.json")
        self.cache = self._load_cache()

    def _load_cache(self):
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return OrderedDict(data)
            except Exception as e:
                logger.error(f"[MemeCache] 加载失败: {e}")
        return OrderedDict()

    def _save_cache(self):
        try:
            # 🛡️ 限制缓存上限，默认 500 条
            limit = self.config.get("cache_limit", 500)
            while len(self.cache) > limit:
                self.cache.popitem(last=False)
            
            with open(self.cache_path, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"[MemeCache] 保存失败: {e}")

    @filter.on_decorating_result()
    async def handle_meme_cache(self, event: AstrMessageEvent):
        """
        全自动监听：在消息发送给 AI 之前，自动注入已有的表情包描述。
        """
        # 1. 提取消息链中的所有表情/图片标识
        chain = event.get_messages()
        meme_keys = []
        for c in chain:
            c_name = c.__class__.__name__
            if c_name == 'Face': meme_keys.append(f"face_{c.id}")
            elif c_name == 'MarketFace': meme_keys.append(f"market_{c.id}")
            elif c_name == 'Image': 
                # 优先使用 file_id，没有则用 url
                key = getattr(c, 'file_id', None) or getattr(c, 'url', None)
                if key: meme_keys.append(f"img_{key}")

        if not meme_keys: return

        # 2. 查找缓存并注入描述
        found_descriptions = []
        for key in meme_keys:
            if key in self.cache:
                found_descriptions.append(self.cache[key])

        if found_descriptions:
            desc_text = " [系统自动识别表情包: " + " | ".join(found_descriptions) + "]"
            # 将描述注入到 raw_message 中，让 AI 能“看见”
            if event.message_obj:
                raw = str(event.message_obj.raw_message)
                event.message_obj.raw_message = raw + desc_text
            logger.info(f"[MemeCache] 成功自动注入描述: {desc_text}")

    @llm_tool(name="cache_meme_description")
    async def cache_meme_description(self, event: AstrMessageEvent, description: str):
        """
        将当前消息中的表情包描述存入缓存。
        
        Args:
            description (string): 对表情包的文字描述。
        """
        chain = event.get_messages()
        added_count = 0
        for c in chain:
            c_name = c.__class__.__name__
            key = None
            if c_name == 'Face': key = f"face_{c.id}"
            elif c_name == 'MarketFace': key = f"market_{c.id}"
            elif c_name == 'Image': key = getattr(c, 'file_id', None) or getattr(c, 'url', None)
            
            if key:
                # 存入缓存（如果已存在则更新）
                self.cache[key] = str(description)
                # 将该 key 移到末尾（表示最近使用过）
                self.cache.move_to_end(key)
                added_count += 1
        
        if added_count > 0:
            self._save_cache()
            return f"✅ 成功！我已经自动记住了这 {added_count} 个表情包。以后只要你发它们，我就能立马认出来啦。"
        return "消息中未找到表情包，我没法记呀。"
