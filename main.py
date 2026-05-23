from astrbot.api.event import filter, AstrMessageEvent, MessageChain
from astrbot.api.star import Context, Star, register
from astrbot.api.all import *
import logging
import json
import os
from collections import OrderedDict

logger = logging.getLogger("astrbot")

@register("meme_cache_guard", "夕小柠 & 陆渊", "表情包缓存卫兵：识别一次，终身受益。省钱省算力。", "2.0.0")
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
            with open(self.cache_path, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"[MemeCache] 保存失败: {e}")

    @filter.on_decorating_result()
    async def handle_meme_cache(self, event: AstrMessageEvent):
        chain = event.get_messages()
        meme_keys = []
        for c in chain:
            c_name = c.__class__.__name__
            if c_name == 'Face': meme_keys.append(f"face_{c.id}")
            elif c_name == 'MarketFace': meme_keys.append(f"market_{c.id}")
            elif c_name == 'Image': 
                key = getattr(c, 'file_id', None) or getattr(c, 'url', None)
                if key: meme_keys.append(f"img_{key}")

        if not meme_keys: return

        new_descriptions = []
        for key in meme_keys:
            if key in self.cache:
                new_descriptions.append(self.cache[key])

        if new_descriptions:
            desc_text = " [表情包描述: " + " | ".join(new_descriptions) + "]"
            if hasattr(event.message_obj, 'raw_message'):
                event.message_obj.raw_message += desc_text
            logger.info(f"[MemeCache] 命中缓存: {desc_text}")

    @llm_tool(name="cache_meme_description")
    async def cache_meme_description(self, event: AstrMessageEvent, description: str):
        '''
        将当前消息中的表情包描述存入缓存。
        参数 description: 对表情包的文字描述。
        '''
        chain = event.get_messages()
        added_count = 0
        for c in chain:
            c_name = c.__class__.__name__
            key = None
            if c_name == 'Face': key = f"face_{c.id}"
            elif c_name == 'MarketFace': key = f"market_{c.id}"
            elif c_name == 'Image': key = getattr(c, 'file_id', None) or getattr(c, 'url', None)
            
            if key:
                self.cache[key] = description
                limit = self.config.get("cache_limit", 500)
                while len(self.cache) > limit:
                    self.cache.popitem(last=False)
                added_count += 1
        
        if added_count > 0:
            self._save_cache()
            return f"成功缓存了 {added_count} 个表情包描述。"
        return "消息中未找到表情包。"
