import importlib
import json

from django.db import models
from jsonfield import JSONField
import requests
from wechatpy import replies

from . import MessageHandler, ReplyMsgType

class Reply(models.Model):
    handler = models.ForeignKey(MessageHandler, on_delete=models.CASCADE,
        related_name="replies")

    msg_type = models.CharField(max_length=16)
    content = models.TextField()
    ext_info = JSONField() # json

    def reply(self, message):
        """
        :type message: wechatpy.messages.BaseMessage

        :returns: serialized xml response
        """
        if self.msg_type == ReplyMsgType.FORWARD:
            # 转发业务
            resp = requests.post(self.content, message.raw, timeout=4.5)
            resp.raise_for_status()
            return resp.content
        elif self.msg_type == ReplyMsgType.CUSTOM:
            # 自定义业务
            try:
                mod_name, func_name = self.content.rsplit('.', 1)
                mod = importlib.import_module(mod_name)
                func = getattr(mod, func_name)
            except:
                pass # TODO: 404
                return ""
            else:
                reply = func(message)
                if not reply:
                    return ""
                reply.source = message.target
                reply.target = message.source
        else:
            # 正常回复类型
            if self.msg_type == ReplyMsgType.NEWS:
                klass = replies.ArticlesReply
                data = dict(articles=json.loads(self.content))
            elif self.msg_type == ReplyMsgType.MUSIC:
                klass = replies.MusicReply
                data = dict(
                    **json.loads(self.content),
                    **self.ext_info
                )
            elif self.msg_type == ReplyMsgType.VIDEO:
                klass = replies.VideoReply
                data = dict(
                    media_id=self.content,
                    **self.ext_info
                )
            elif self.msg_type == ReplyMsgType.IMAGE:
                klass = replies.ImageReply
                data = dict(media_id=self.content)
            elif self.msg_type == ReplyMsgType.VOICE:
                klass = replies.VoiceReply
                data = dict(media_id=self.content)
            else:
                klass = replies.TextReply
                data = dict(content=self.content)
            reply = klass(message=message, **data)
        return reply.render()

    @classmethod
    def from_mp(cls, data):
        type = data["type"]
        reply = cls(
            msg_type=type
        )
        if type in (ReplyMsgType.TEXT, ReplyMsgType.IMAGE, ReplyMsgType.VOICE, 
            ReplyMsgType.VIDEO):
            # TODO: 图片回复说是img
            reply.content = content
        elif type == ReplyMsgType.NEWS:
            news = list(map(lambda o: dict(
                title=o["title"],
                description=o.get("digest") or "",
                image=o["cover_url"],
                url=o["content_url"]
            ), data["news_info"]["list"]))
            reply.content = json.dumps(news)
        else:
            # TODO: unknown type
            raise Exception()
        reply.save()