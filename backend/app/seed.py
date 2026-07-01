from app.core.database import execute, query_one, to_json
from app.core.enums import Permission, SystemSettingKey, UserStatus


PROTOTYPE_RULE_VERSIONS = {
    "QG2": "V01",
    "QG3.1": "V01",
    "QG3.2": "V01",
    "QG3.3": "V14",
    "QG3": "V01",
    "QG4": "V01",
}


PROTOTYPE_RULE_DATA = {
    "QG2": {
        "ai": [
            ("QG2:PROCESS_PLAN", "过程开发计划", "ai-exist", "MP Kick-off / 过程开发计划&风险清单", "Project Plan/项目开发/项目计划", "输出过程开发计划", "single_template", "MP"),
            ("QG2:BOOM_VIEW", "产品爆炸图", "ai-content", "MP Kick-off", "Kickoff/制造过程开发", "产品爆炸图", "single_template", "MP"),
        ],
        "manual": [
            ("QG2:HISTORY_ISSUES", "过往问题点", "是否输出制造过往问题点清单", "MQD"),
            ("QG2:DFA_PLAN", "DFA评审策划", "是否输出 DFA 评审计划", "PT"),
            ("QG2:DFT_PLAN", "DFT评审策划", "是否输出 DFT 评审计划", "TE"),
            ("QG2:NUDD", "制造过程新颖性变更", "PQM是否组织完成NUDD识别", "MQD"),
        ],
    },
    "QG3.1": {
        "ai": [
            ("QG3.1:DFA_LIST", "DFA", "ai-exist", "DFM、DFA、DFT", "DFA", "是否输出 DFA 评审问题清单", "single_template", "PT"),
            ("QG3.1:DFT_LIST", "DFT", "ai-exist", "DFM、DFA、DFT", "DFT", "是否已输出 DFT 评审问题清单", "single_template", "TE"),
            ("QG3.1:SPECIAL_CHARACTERISTICS", "过程特殊特性", "ai-exist", "产品&过程特殊特性清单", "SC/过程特殊特性清单/特殊特性", "收到产品SC并转化为过程SC", "single_template", "MP"),
            ("QG3.1:FLOW_CHART", "流程图", "ai-exist", "Flow chart", "FC/工艺流程图/流程图", "初始的流程图发布在PLM系统", "single_template", "PT"),
            ("QG3.1:PFMEA", "PFMEA", "ai-exist", "PFMEA", "PFMEA", "初始的PFAMA发布在PLM系统", "single_template", "MP"),
            ("QG3.1:TOOLING_PLAN", "工装设备开发计划", "ai-content", "装配工装和配件release file", "工装需求表", "提供装配/测试/ICT的工装开发计划", "single_template", "PT/TE"),
        ],
        "manual": [
            ("QG3.1:HISTORY_ISSUES", "过往问题点", "是否按计划实施并验证有效？", "MQD"),
            ("QG3.1:NUDD", "制造过程新颖性变更", "是否完成初始清单识别？", "MQD"),
        ],
    },
    "QG3.2": {
        "ai": [
            ("QG3.2:PIL", "PIL问题", "system", "QMS 系统", "", "关闭率70%，不允许有红色问题", "single_template", "MP"),
            ("QG3.2:NUDD", "制造过程新颖性变更", "ai-exist", "新工艺，新零件过程认可", "", "是否有按照计划验证？", "folder_non_empty", "MP"),
            ("QG3.2:DFA_CLOSURE_A", "DFA", "ai-content", "DFM、DFA、DFT", "DFA", " A类问题是否按计划关闭？", "single_template", "PT"),
            ("QG3.2:DFT_CLOSURE_A", "DFT", "ai-content", "DFM、DFA、DFT", "DFT", "A类问题是否按计划关闭？", "single_template", "TE"),
            ("QG3.2:SPECIAL_CHARACTERISTICS", "过程特殊特性", "ai-content", "产品&过程特殊特性清单", "SC/过程特殊特性清单/特殊特性", " SC清单是否更新？且有管控方法", "single_template", "MP"),
            ("QG3.2:FLOW_CHART_FRESHNESS", "流程图", "ai-content", "Flow chart", "FC/工艺流程图/流程图", "/确认是否在PLM系统进行更新？", "freshness_check", "PT"),
            ("QG3.2:PFMEA_FRESHNESS", "PFMEA", "ai-content", "PFMEA", "PFMEA", "确认是否在PLM系统进行更新？", "freshness_check", "MP"),
            ("QG3.2:TOOLING_PLAN_FRESHNESS", "工装设备开发计划", "ai-content", "装配工装和配件release file", "工装需求表", "确认工装设备计划是否Delay？", "freshness_check", "PT/TE"),
        ],
        "manual": [
            ("QG3.2:DEFECT_RATE", "不良率", "不良率是否达标？", "PT"),
            ("QG3.2:FALSE_TEST_RATE", "误测率", "误测率是否达标？", "TE"),
            ("QG3.2:HISTORY_ISSUES", "过往问题点", "是否按计划实施并验证有效？", "MQD"),
        ],
    },
    "QG3.3": {
        "ai": [
            ("QG3.3:PIL", "PIL 问题", "system", "QMS 系统", "", "关闭率80%，不允许有红/黄问题", "single_template", "MP"),
            ("QG3.3:NUDD", "制造过程新颖性变更", "ai-exist", "新工艺，新零件过程认可", "", "是否有按照计划验证？", "folder_non_empty", "MP"),
            ("QG3.3:DFA_CLOSURE_ABC", "DFA", "ai-content", "DFM、DFA、DFT", "DFA", "A/B/C 类问题是否按计划关闭？", "single_template", "PT"),
            ("QG3.3:DFT_CLOSURE_ABC", "DFT", "ai-content", "DFM、DFA、DFT", "DFT", "A/B/C 类问题是否按计划关闭？", "single_template", "TE"),
            ("QG3.3:MSA_PLAN", "MSA 计划", "ai-exist", "MSA", "MSA", "输出MSA计划", "single_template", "TE"),
            ("QG3.3:FLOW_CHART_FRESHNESS", "流程图", "ai-content", "Flow chart", "确认是否有更新？", "确认是否有更新？", "freshness_check", "PT"),
            ("QG3.3:PFMEA_FRESHNESS", "PFMEA", "ai-content", "PFMEA", "PFMEA", "确认是否有更新？", "freshness_check", "MP"),
            ("QG3.3:CP_EXISTENCE", "CP", "ai-exist", "Control plan", "CP/控制计划", "输出初版文件", "summary_file", "MP"),
            ("QG3.3:TOOLING_ACCEPTANCE", "设备/工装验收报告", "ai-exist", " 输出部分工装验收报告", "工装验收", "先命中字眼；含字眼文件存在即满足", "single_template", "PT/TE"),
            ("QG3.3:POKAYOKE_COVERAGE", "防错覆盖率分析表", "ai-content", "Pokayoke清单", "防错覆盖率", "输出初版防错覆盖率分析表", "single_template", "PT"),
        ],
        "manual": [
            ("QG3.3:DEFECT_RATE", "不良率", "不良率是否达标？", "PT"),
            ("QG3.3:FALSE_TEST_RATE", "误测率", "误测率是否达标？", "TE"),
            ("QG3.3:HISTORY_ISSUES", "过往问题点", "是否按计划实施并验证有效？", "MQD"),
            ("QG3.3:SPECIAL_CHARACTERISTICS_MANUAL", "过程特殊特性", "SC的管控方法是否可行？比如SPC管控方法的CPK能力合格", "MP"),
            ("QG3.3:DIAG_COMMAND_VALIDATION", "诊断指令有效性验证清单", "工程师人工核查", "TE"),
        ],
    },
    "QG3": {
        "ai": [
            ("QG3:PIL", "PIL问题", "system", "QMS 系统", "", "关闭率：90%不允许有红黄蓝问题", "single_template", "MP"),
            ("QG3:NUDD_CLOSED", "制造过程新颖性变更", "ai-content", "新工艺，新零件过程认可", "", "风险项100% 关闭？", "folder_non_empty", "MP"),
            ("QG3:FLOW_CHART_FRESHNESS", "流程图", "ai-content", "Flow chart", "FC/工艺流程图/流程图", "文件有无更新？", "freshness_check", "PT"),
            ("QG3:PFMEA_FRESHNESS", "PFMEA", "ai-content", "PFMEA", "PFMEA", "确认是否有更新？", "freshness_check", "MP"),
            ("QG3:CP_FRESHNESS", "CP", "ai-content", "Control plan", "CP/控制计划", "文件是否更新？", "summary_file", "MP"),
            ("QG3:PATS_CP_CONSISTENCY", "PATS与CP一致性确认", "ai-content", "PATS / Control plan", "PATS/CP/控制计划", "PATS参数与CP是否一致？", "summary_file", "MP"),
            ("QG3:TOOLING_ACCEPTANCE", "设备/工装验收报告", "ai-exist", "装配工装和配件release file", "工装验收", "输出所有工装设备验收报告", "single_template", "PT/TE"),
            ("QG3:POKAYOKE_COVERAGE", "防错覆盖率分析表", "ai-content", "Pokayoke清单", "防错覆盖率", "防错覆盖率100%（除了包装和打螺丝工位）", "single_template", "PT"),
            ("QG3:PROCESS_POKAYOKE_LIST", "过程防错清单", "ai-exist", "Poka yoke清单", "过程防错清单", "发布生产过程防错清单", "single_template", "PT"),
            ("QG3:FUNCTION_COVERAGE", "功能覆盖率", "ai-content", "功能覆盖率报告", "功能覆盖率", "功能测试100%覆盖过往问题库、PTS、产品Spec、防错清单中的项目", "single_template", "TE"),
            ("QG3:AOI_COVERAGE", "贴片元件AOI测试覆盖率分析表", "ai-exist", "SMD贴片元件AOI覆盖率报告", "覆盖率", "输出元件AOI测试覆盖率分析表", "single_template", "TE"),
        ],
        "manual": [
            ("QG3:DEFECT_RATE", "不良率", "不良率是否达标？", "PT"),
            ("QG3:FALSE_TEST_RATE", "误测率", "误测率是否达标？", "TE"),
            ("QG3:SPECIAL_CHARACTERISTICS_MANUAL", "过程特殊特性", "工程师人工核查", "MP"),
            ("QG3:MSA_REPORT", "MSA报告", " MSA报告符合要求", "TE"),
            ("QG3:HISTORY_ISSUES", "过往问题点", "措施是否100%落实？", "MQD"),
            ("QG3:MES", "MES", "工程师人工核查", "TE"),
        ],
    },
    "QG4": {
        "ai": [
            ("QG4:PIL", "PIL问题", "system", "QMS 系统", "", "关闭率：100%不允许有红/黄/蓝/紫问题", "single_template", "MP"),
            ("QG4:PFMEA_FRESHNESS", "PFMEA", "ai-content", "PFMEA", "PFMEA", "确认是否在PLM系统进行更新？", "freshness_check", "MP"),
            ("QG4:UCM_SOP_FA", "量产SOP", "system", "UCM 系统", "绘图总号", "输出终版文件", "single_template", "MP"),
            ("QG4:PLM_THREE_DOCS_RELEASE", "三大文件在PLM系统发布", "system", "PLM 系统", "", "确认是否完成PLM系统发布", "single_template", "MP"),
            ("QG4:POKAYOKE_FUNCTION_CHECK", "防错功能检查表", "ai-exist", "Poka yoke清单", "防错功能检查表", "发布防错功能检查表", "single_template", "PT"),
            ("QG4:COMPONENT_COVERAGE", "元件覆盖率", "ai-exist", "SMD贴片元件AOI测试覆盖率报告", "覆盖率", "完成元件覆盖率表中ICT部分", "single_template", "TE"),
            ("QG4:NEW_PROCESS_APPROVAL_REPORT", "新工艺过程认可报告", "ai-exist", "新工艺，新零件过程认可", "", "输出新工艺的过程认可报告", "folder_non_empty", "MP"),
        ],
        "manual": [
            ("QG4:INHERIT_HISTORY_ISSUES", "过往问题点", "100%落实", "MQD"),
            ("QG4:INHERIT_NUDD", "制造过程新规性变更", "风险项100%关闭", "MP"),
            ("QG4:INHERIT_DFA", "DFA", "问题100%关闭", "PT"),
            ("QG4:INHERIT_DFT", "DFT", "问题100%关闭", "TE"),
            ("QG4:INHERIT_SPECIAL_CHARACTERISTICS", "过程特殊特性", "继承前序节点结论", "MP"),
            ("QG4:INHERIT_MSA_REPORT", "MSA报告", "输出终版报告", "TE"),
            ("QG4:INHERIT_FLOW_CHART", "流程图", "确认是否在PLM系统进行更新？", "PT"),
            ("QG4:INHERIT_TOOLING_ACCEPTANCE", "设备/工装验收报告", "输出终版文件", "PT/TE"),
            ("QG4:INHERIT_POKAYOKE_COVERAGE", "防错覆盖率分析表", "防错覆盖率100%（除了包装和打螺丝工位）", "PT"),
            ("QG4:INHERIT_FUNCTION_COVERAGE", "功能覆盖率", "功能测试100%覆盖过往问题库、PTS、产品SpeC、防错清单中的项目", "TE"),
            ("QG4:DEFECT_RATE", "不良率", "不良率是否达标？", "PT"),
            ("QG4:FALSE_TEST_RATE", "误测率", "误测率是否达标？", "TE"),
            ("QG4:CP_MANUAL", "CP", "确认是否在PLM系统进行更新？", "MP"),
            ("QG4:CP_SOP_SITE_CONSISTENCY", "CP/SOP/现场工艺一致性确认", "问题100%关闭", "MP"),
            ("QG4:MES", "MES", "全功能上线", "TE"),
        ],
    },
}


def split_keywords(raw_keywords: str) -> list[str]:
    return [keyword.strip() for keyword in raw_keywords.split("/") if keyword.strip()]


def rule_type_from_prototype(prototype_type: str) -> tuple[str, str]:
    if prototype_type == "ai-exist":
        return "auto", "file_existence"
    if prototype_type == "ai-content":
        return "auto", "content_check"
    if prototype_type == "system":
        return "system", "system_direct"
    return "manual", "manual"


def seed_prototype_rules() -> None:
    for node_code, groups in PROTOTYPE_RULE_DATA.items():
        qg_node = query_one("SELECT id FROM qg_nodes WHERE node_code = ?", (node_code,))
        if not qg_node:
            continue
        if query_one("SELECT id FROM business_rule_versions WHERE qg_node_id = ? LIMIT 1", (qg_node["id"],)):
            continue
        version = execute(
            """
            INSERT INTO business_rule_versions(
                qg_node_id, version_no, status, change_summary, published_by, published_at, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                qg_node["id"],
                PROTOTYPE_RULE_VERSIONS[node_code],
                "published",
                "原型规则初始化",
                1,
                "2026-03-26 00:00:00",
                1,
            ),
        )
        sort_order = 1
        for rule in groups["ai"]:
            rule_code, item_name, prototype_type, location, keywords, requirement, strategy, owner = rule
            item_type, check_type = rule_type_from_prototype(prototype_type)
            rule_id = insert_prototype_business_rule(
                version.lastrowid,
                qg_node["id"],
                rule_code,
                item_name,
                item_type,
                check_type,
                requirement,
                owner,
                sort_order,
            )
            insert_prototype_execution_rule(
                rule_id,
                rule_code,
                check_type,
                {
                    "mock": True,
                    "source": "prototype",
                    "location": location,
                    "keywords": split_keywords(keywords),
                    "strategy": strategy,
                },
            )
            sort_order += 1
        for rule_code, item_name, requirement, owner in groups["manual"]:
            insert_prototype_business_rule(
                version.lastrowid,
                qg_node["id"],
                rule_code,
                item_name,
                "manual",
                "manual",
                requirement,
                owner,
                sort_order,
            )
            sort_order += 1


def insert_prototype_business_rule(
    version_id: int,
    qg_node_id: int,
    rule_code: str,
    item_name: str,
    item_type: str,
    check_type: str,
    checklist_requirement: str,
    owner_dept: str,
    sort_order: int,
) -> int:
    result = execute(
        """
        INSERT INTO business_check_rules(
            business_rule_version_id, qg_node_id, rule_code, item_name, item_type,
            check_type, checklist_requirement, owner_dept, is_apqp, is_active, sort_order
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 1, ?)
        """,
        (
            version_id,
            qg_node_id,
            rule_code,
            item_name,
            item_type,
            check_type,
            checklist_requirement,
            owner_dept,
            sort_order,
        ),
    )
    return int(result.lastrowid)


def insert_prototype_execution_rule(rule_id: int, rule_code: str, check_type: str, config: dict) -> None:
    execute(
        """
        INSERT INTO auto_check_execution_rules(
            business_check_rule_id, execution_code, execution_mode, adapter_type,
            config_json, config_version, is_enabled, created_by
        ) VALUES (?, ?, ?, ?, ?, ?, 1, ?)
        """,
        (
            rule_id,
            f"{rule_code}:EXEC",
            check_type,
            "mock_system" if check_type == "system_direct" else "vdrive",
            to_json(config),
            "V1",
            1,
        ),
    )


def seed_database() -> None:
    if not query_one("SELECT id FROM users WHERE uid = ?", ("admin",)):
        execute(
            "INSERT INTO users(uid, name, email, status) VALUES (?, ?, ?, ?)",
            ("admin", "系统管理员", "admin@example.com", UserStatus.ACTIVE),
        )
        admin = query_one("SELECT id FROM users WHERE uid = ?", ("admin",))
        for permission in (Permission.SUPER_ADMIN, Permission.INSPECTION_ENGINEER, Permission.RULES_ADMIN, Permission.PROJECT_ADMIN):
            execute(
                "INSERT INTO user_permissions(user_id, permission_code) VALUES (?, ?)",
                (admin["id"], permission),
            )

    for sort_order, code in enumerate(("QG2", "QG3.1", "QG3.2", "QG3.3", "QG3", "QG4"), start=1):
        if not query_one("SELECT id FROM qg_nodes WHERE node_code = ?", (code,)):
            execute(
                "INSERT INTO qg_nodes(node_code, sort_order) VALUES (?, ?)",
                (code, sort_order),
            )

    if not query_one("SELECT key FROM system_settings WHERE key = ?", (SystemSettingKey.AUTO_CHECK_ENABLED,)):
        execute(
            "INSERT INTO system_settings(key, value_json, saved_by) VALUES (?, ?, ?)",
            (SystemSettingKey.AUTO_CHECK_ENABLED, to_json(True), 1),
        )

    seed_prototype_rules()
