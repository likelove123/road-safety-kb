"""敏感信息脱敏：车牌、身份证、姓名。

规则（按答辩要求）：
- 车牌：地域简称 + 字母 + xxxxx，如 粤B50321 → 粤Bxxxxx
- 身份证：保留前 3 位与后 4 位，中间改 *，如 430123456789012345 → 430***********2345
- 姓名：只保留姓氏，其余改“某”，如 李华 → 李某
"""
import re

# 省级简称（车牌首位）
_PROV = "京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼"

# 车牌：粤B50321 / 京A12345 / 粤BD12345（新能源）
PLATE_RE = re.compile(rf"([{_PROV}])([A-Za-z])[A-Za-z0-9]{{5,6}}")

# 身份证：18 位（末位可为 X）与 15 位
ID18_RE = re.compile(r"(?<!\d)(\d{3})\d{11}([\dXx]{4})(?!\d)")
ID15_RE = re.compile(r"(?<!\d)(\d{3})\d{8}(\d{4})(?!\d)")

# 常见姓氏（用于姓名识别）
_SURNAMES = (
    "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜戚谢邹喻柏水窦章"
    "云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳鲍史唐费廉岑薛雷贺倪汤滕殷罗毕郝邬安常"
    "乐于时傅皮卞齐康伍余元卜顾孟平黄和穆萧尹姚邵湛汪祁毛禹狄米贝明臧计伏成戴谈宋茅"
    "庞熊纪舒屈项祝董梁杜阮蓝闵席季麻强贾路娄危江童颜郭梅盛林刁钟徐邱骆高夏蔡田樊胡"
    "凌霍虞万支柯昝管卢莫经房裘缪干解应宗丁宣贲邓郁单杭洪包诸左石崔吉钮龚程嵇邢滑裴"
    "陆荣翁荀羊於惠甄曲家封芮羿储靳汲邴糜松井段富巫乌焦巴弓牧隗山谷车侯宓蓬全郗班仰"
    "秋仲伊宫宁仇栾暴甘钭厉戎祖武符刘景詹束龙叶幸司韶郜黎蓟薄印宿白怀蒲邰从鄂索咸籍"
    "赖卓蔺屠蒙池乔阴胥能苍双闻莘党翟谭贡劳逄姬申扶堵冉宰郦雍桑桂濮牛寿通边扈燕冀郏"
    "浦尚农温别庄晏柴瞿阎充慕连茹习宦艾鱼容向古易慎戈廖庾终暨居衡步都耿满弘匡国文寇"
    "广禄阙东欧殳沃利蔚越夔隆师巩聂晁勾敖融冷訾辛阚那简饶空曾毋沙乜养鞠须丰巢关蒯相"
    "查后荆红游竺权逯盖益桓公"
)
_NAME = "[" + _SURNAMES + r"][\u4e00-\u9fa5]{1,2}"

# “姓名：李华”“驾驶员：张伟”这类带角色/字段的姓名
NAME_CTX_RE = re.compile(
    rf"(姓名|姓\s*名|驾驶员|驾驶人|司机|车主|押运员|押运人员|安全员|责任人|当事人|"
    rf"负责人|主要负责人|联系人|乘客|伤者|死者)\s*[：:]\s*({_NAME})(?=[，,。;；、\s）)]|$)"
)
# “乘客李华受伤”“当事人张伟承担”这类角色后直接跟姓名、再接动作的写法
NAME_ROLE_RE = re.compile(
    rf"(驾驶员|驾驶人|司机|车主|押运员|押运人员|安全员|责任人|当事人|负责人|主要负责人|"
    rf"联系人|乘客|伤者|死者)({_NAME})(?=(受伤|死亡|驾驶|连续|系|为|承担|负|所有|承包|雇佣|聘用|随车|乘坐))"
)


def mask_plate(text: str) -> str:
    """车牌脱敏：保留地域简称和发牌机关字母，其余改 x。"""
    return PLATE_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}xxxxx", text)


def mask_id_card(text: str) -> str:
    """身份证脱敏：前 3 位 + * + 后 4 位。"""
    text = ID18_RE.sub(lambda m: f"{m.group(1)}{'*' * 11}{m.group(2)}", text)
    return ID15_RE.sub(lambda m: f"{m.group(1)}{'*' * 8}{m.group(2)}", text)


def mask_name(name: str) -> str:
    """单个姓名脱敏：保留姓氏，名字改为“某”。"""
    name = name.strip()
    if len(name) < 2:
        return name
    return name[0] + "某"


def mask_text(text: str) -> str:
    """对整段文本做车牌、身份证、姓名脱敏，可重复调用（幂等）。"""
    if not text:
        return text
    text = mask_id_card(text)
    text = mask_plate(text)
    text = NAME_CTX_RE.sub(lambda m: f"{m.group(1)}：{mask_name(m.group(2))}", text)
    text = NAME_ROLE_RE.sub(lambda m: f"{m.group(1)}{mask_name(m.group(2))}", text)
    return text


def desensitize_case(case_text: str) -> str:
    """案情文本脱敏，送模型前与展示前都调用它。"""
    return mask_text(case_text)
