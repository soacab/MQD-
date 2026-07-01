# Design

## Design Tokens

CheckFlow 采用原型中的产品工具风格：浅灰页面底、白色工作面、低圆角、细边框、克制阴影和蓝紫主色。

- Base background: `--cf-bg-base`
- Surface: `--cf-bg-surface`
- Primary: `--cf-primary-700`
- Text: `--cf-text-primary`, `--cf-text-secondary`, `--cf-text-tertiary`
- Border: `--cf-border-default`, `--cf-border-subtle`
- Radius: 3px, 5px, 8px
- Font: system UI plus `Noto Sans SC` compatible Chinese fallback

## Top Navigation

全局顶栏承载 CheckFlow 品牌、工作台、规则配置、检查档案、点检任务、整改复查和后台管理。头像/后台入口属于 4.1 账号管理入口语义；当前前端保留显式后台管理入口，后续可改为头像下拉。

## Status Vocabulary

- 满足 / FULL-GO: pass
- 不满足 / NO-GO: fail
- 带条件满足 / C-GO: conditional
- 不适用: info
- 待确认、检查中、无法自动判断、已确认: neutral or warning by state

状态标签必须同时展示文字，不只靠颜色。

## Layout Rules

工作台使用任务分区看板。点检执行页使用顶部上下文加三栏布局：检查项导航、检查项详情、工程师操作区。检查档案使用筛选工具条、密集表格和详情弹窗。规则配置使用左侧 QG 节点导航和右侧规则表。

## Field Governance

第四章和 `CheckFlow_原型.html` 共同决定字段进入 UI 的资格。接口为实现现状。待确认差异不擅自展示，统一在差异文档和页面治理提示中说明。

## Components

按钮、输入框、表格、弹窗、提示条和标签统一使用低圆角与细边框。主要按钮用于提交、开始执行、确认归档和触发复查；次要按钮用于筛选、查看、返回和取消；危险按钮用于删除、作废和停用。
