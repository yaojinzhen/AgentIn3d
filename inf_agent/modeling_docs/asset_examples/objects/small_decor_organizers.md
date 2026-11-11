---
id: small-decor-organizers-native
domain: object
intent: 挂钩、花瓶、书本、书堆和小型收纳件的原生路线
aliases: ["hook", "vase", "book", "book stack", "book column", "basket", "plate rack", "挂钩", "花瓶", "书本", "书堆", "收纳篮", "盘架"]
use_when: "创建可独立摆放或安装的小型家居装饰、书本或规则收纳件。"
avoid_when: "目标是包含大量随机摆件的完整货架场景，或需要群落散布的自然装饰。"
source_symbols: ["infinigen/assets/objects/organizer/hook.py:HookBaseFactory", "infinigen/assets/objects/table_decorations/vase.py:VaseFactory", "infinigen/assets/objects/table_decorations/book.py:BookFactory", "infinigen/assets/objects/table_decorations/book.py:BookStackFactory", "infinigen/assets/objects/table_decorations/book.py:BookColumnFactory", "infinigen/assets/objects/organizer/basket.py:BasketBaseFactory", "infinigen/assets/objects/organizer/plate_rack.py:PlateRackBaseFactory"]
related_patterns: ["rigid-assembly", "profile-revolve-shell", "curve-sweep"]
summary: "按对象使用回转、曲线或规则装配；避免调用会随机生成整组摆件的元 Factory。"
---

# 小型装饰与收纳原生参考

花瓶使用 `VaseFactory` 的轮廓放样路线；书本使用 `BookFactory` 的封面、书页和书脊层次；挂钩
使用安装背板与曲线钩体；收纳篮和盘架使用规则框架与重复件。`NatureShelfTrinketsFactory`
会组合多个底层自然 Factory，只适合场景级摆件集合，不是单个小物的默认入口。
