 




基于 HTTP Chunked 协议的单向流式合成接口，一次性输入文本，流式返回音频，支持中、英、日、西等多语种及多种方言口音。

&nbsp;

<span data-label="purple">POST</span> `https://openspeech.bytedance.com/api/v3/tts/unidirectional`


<span id="FB4hcqC8"></span>
### 请求头


**X\-Api\-Key ** `string` <span data-api-tag="require|9gv9Vz">必选</span>

API Key 可以从 [控制台>API Key管理](https://console.volcengine.com/speech/new/setting/apikeys?projectName=default.) 获取



**X\-Api\-Resource\-Id ** `string` <span data-api-tag="require|M22Sxg">必选</span>

请求的模型版本，可选值：


* `seed-tts-2.0`:豆包语音合成大模型2.0，支持使用[豆包语音合成模型2.0音色](https://www.volcengine.com/docs/6561/1257544?lang=zh#%E8%B1%86%E5%8C%85%E8%AF%AD%E9%9F%B3%E5%90%88%E6%88%90%E6%A8%A1%E5%9E%8B2-0-%E9%9F%B3%E8%89%B2%E5%88%97%E8%A1%A8)

* `seed-icl-2.0`:豆包声音复刻大模型2.0，支持使用声音复刻接口克隆的音色，具体音色详见[控制台>音色库](https://console.volcengine.com/speech/new/voices?projectName=default)



**X\-Api\-Request\-Id ** `string` <span data-api-tag="require|M22Sxg">必选</span>

标识客户端请求ID，uuid随机字符串



**X\-Control\-Require\-Usage\-Tokens\-Return ** `string`

若设置为`*`，会返回计费的字符数




<span id="sFZZSkH5"></span>
### 请求体


**req_params ** `object` <span data-api-tag="require|SL5CNq">必选</span>


**text ** `string` <span data-api-tag="require|uo2J0a">必选</span>

待合成的输入文本



**model** `string`

具体模型版本，当`speaker`参数为复刻音色时使用，默认值：


* `seed-tts-2.0-standard`

   * 不支持使用语音指令`context_texts`



**speaker** `string` <span data-api-tag="require|dQHTIf">必选</span>

音色 ID，可从[控制台 > 音色库](https://console.volcengine.com/speech/new/voices?projectName=default)获取



**ssml** `string`

SSML 标记文本，启用后按 SSML 规则解析 `text`


* 目前仅中英文音色支持ssml，音色详见：[豆包语音合成模型2.0音色](https://www.volcengine.com/docs/6561/1257544?lang=zh#%E8%B1%86%E5%8C%85%E8%AF%AD%E9%9F%B3%E5%90%88%E6%88%90%E6%A8%A1%E5%9E%8B2-0-%E9%9F%B3%E8%89%B2%E5%88%97%E8%A1%A8)


详见：[SSML标记语言](https://www.volcengine.com/docs/6561/1330194?lang=zh)



**audio_params** `object` <span data-api-tag="require|TpaG6z">必选</span>

音频参数


**format** `string`

音频格式，支持 `mp3` / `pcm` / `ogg_opus` / `wav`

默认值：`mp3`

注意：流式场景推荐使用`pcm`，不建议使用`wav`



**sample_rate** `int`

音频采样率，单位 Hz，可选值：

[`8000`,`16000`,`22050`,`24000`,`32000`,`44100`,`48000`]


&nbsp;


**bit_rate** `int`

音频比特率，单位 bps，默认范围[`64000`,`160000`]

注意：该参数仅对 `mp3` 格式的音频生效



**speech_rate** `int`

语速，取值范围 [`-50`, `100`]，其中，取值`100`代表2.0倍速，`-50`代表0.5倍速



**loudness_rate** `int`

音量，取值范围 [`-50`, `100`]，其中，取值`100`代表2.0倍音量，`-50`代表0.5倍音量



**enable_subtitle** `bool`

是否开启字幕服务，开启后，返回字级别的时间戳

可选值：`true`, `false`

默认值：`false`

&nbsp;

注意：


* 仅豆包语音合成大模型2.0支持该参数

* 目前该参数仅支持中文、英文




**additions** `string` 


**max_length_to_filter_parenthesis ** `int`

是否过滤括号内的部分，0为不过滤，100为过滤



**silence_duration** `int`

在文本末尾增加静音时长，单位 ms

范围：[`0`,`30000`]

默认值：`0`



**disable_markdown_filter** `bool`

是否开启 Markdown解析过滤

`true`：开启过滤，会解析并去除 Markdown 语法。例如" \*\*你好\*\* "朗读为 "你好"

`false`：关闭过滤，保留原始字符。例如 " \*\*你好\*\* " 朗读为 "星星你好星星"

默认值：`false`



**disable_emoji_filter** `bool`

是否开启Emoji解析过滤

可选值：`true`, `false`

默认值：`false`



**enable_latex_tn** `bool`

是否启用 Latex文本朗读能力

可选值：`true`, `false`

默认值：`false`



**latex_parser** `string`

是否启用更强的Latex文本朗读能力

可选值：`v2`

注意：


* 该参数适用于教育场景，启用该参数后，时延会增加

* 开启该参数时，需将`disable_markdown_filter`设置为`true`



**explicit_language** `string`

显式指定朗读语种。开启后，仅朗读指定语种的文本，其他语种的内容会被跳过或合成失败，取值如下


* `zh-cn`：中文为主，支持中英混读

* `en`：仅朗读英语

* `ja`：仅朗读日语

* `es-mx`：仅朗读墨西哥语

* `id`：仅朗读印度尼西亚语

* `pt-br`：仅朗读巴西葡萄牙语

* `pt`：仅朗读葡萄牙语

* `ko`：仅朗读韩语

* `it`：仅意大利语

* `de`：仅德语

* `fr`：仅法语

* `th`：仅泰语

* `vi`：仅越南语

* `ru`：仅俄语

* `fil`：仅菲律宾语

* `ms`：仅马来语

* `ar`：仅阿拉伯语

* `pl`：仅波兰语

* `tr`：仅土耳其语

* `sv`：仅瑞典语


注意：启用该参数后，输入文本须包含指定语种的内容，否则请求将无法正常返回



**explicit_dialect** `string`

指定方言。

&nbsp;

注意：使用该参数时，`speaker`需要设置支持方言的音色，详见[音色列表](https://www.volcengine.com/docs/6561/1257544?lang=zh)



**aigc_watermark** `bool`

AIGC生成标识。开启后，会在音频合成结尾添加节奏标识

默认值：`false`



**aigc_metadata** `object`

在合成音频中添加meta水印，支持音频格式 `mp3` / `wav` / `ogg_opus`


**enable ** `bool`

是否启用meta隐式水印

默认值：`false`



**content_producer ** `string`

合成服务提供者的名称或编码



**produce_id ** `string`

内容制作编号



**content_propagator ** `string`

内容传播服务提供者的名称或编码



**propagate_id ** `string`

内容传播编号






**cache_config** `object`

缓存相关配置


**text_type ** `int`

文本类型标识。需和`use_cache`一起使用，需要开启缓存时取`0`



**use_cache ** `bool`

是否启用缓存。需和`text_type`一起使用，需要开启缓存时传`true`




**post_process** `object`


**pitch ** `int`

音调，取值范围`[-12,12]`




**context_texts** `array`

语音指令。

注意：


* 当`speaker`参数设置为[豆包语音合成模型2.0音色](https://www.volcengine.com/docs/6561/1257544?lang=zh#%E8%B1%86%E5%8C%85%E8%AF%AD%E9%9F%B3%E5%90%88%E6%88%90%E6%A8%A1%E5%9E%8B2-0-%E9%9F%B3%E8%89%B2%E5%88%97%E8%A1%A8)时，可直接使用语音指令

* 当`speaker`参数设置为复刻音色时，暂不支持；

* 该字段文本不参与计费


示例：

```Python
"context_texts":[ "你可以用特别特别痛心的语气说话吗?"]
```




**section_id ** `string`

段落标识，用于跨包语义保持。

注意：该参数支持[豆包语音合成模型2.0音色](https://www.volcengine.com/docs/6561/1257544?lang=zh#%E8%B1%86%E5%8C%85%E8%AF%AD%E9%9F%B3%E5%90%88%E6%88%90%E6%A8%A1%E5%9E%8B2-0-%E9%9F%B3%E8%89%B2%E5%88%97%E8%A1%A8)、豆包声音复刻大模型2.0音色



**tone_fidelity ** **`bool`**

是否开启还原模式，开启后模型将尽可能还原送入的训练的prompt音频音色和说话风格（情感、韵律、口音等）

默认值：`false`

**注意：仅适用于**豆包声音复刻大模型2.0音色，**仅支持**合成和训练音频同语种的文本 **，不支持**跨语种合成 **，不支持**双向流合成接口








<span id="a3OkyUqJ"></span>
### 响应


**X\-Tt\-Logid ** `string`

服务端返回的 logid，用于在咨询或者反馈时定位问题



**code ** `int`

状态码



**message ** `string`

状态详情



**data ** `string`

合成音频数据，base64编码



**sentence ** `object`


**phonemes ** `object`

音素相关时间戳



**text ** `string`

合成音频文本



**words ** `object`

字级别时间戳


**confidence ** `float`

时间戳置信度，范围 0~1



**startTime ** `float`

开始时间（秒）



**endTime ** `float`

结束时间（秒）



**word ** `string`

字





**usage ** `object`

本次请求的资源消耗统计


**text_words ** `int`

本次请求计费的文本字数（含标点）




