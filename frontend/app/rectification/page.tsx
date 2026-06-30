"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  closeFollowup,
  listFollowups,
  listRectifications,
  markRectificationDone,
  triggerRecheck,
  undoRectificationDone,
  type FollowUpItem,
  type RectificationItem
} from "@/lib/api";

export default function RectificationPage() {
  const [taskId, setTaskId] = useState("");
  const [rectifications, setRectifications] = useState<RectificationItem[]>([]);
  const [followups, setFollowups] = useState<FollowUpItem[]>([]);
  const [message, setMessage] = useState("");

  async function refresh(nextTaskId = taskId) {
    try {
      const id = nextTaskId ? Number(nextTaskId) : undefined;
      const [rectificationRows, followupRows] = await Promise.all([listRectifications(id), listFollowups(id)]);
      setRectifications(rectificationRows.items);
      setFollowups(followupRows.items);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "整改数据加载失败");
    }
  }

  useEffect(() => {
    void refresh("");
  }, []);

  async function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await refresh(taskId);
  }

  async function handleMarkDone(itemId: number) {
    if (!confirmRectificationAction("确认将该整改项标记为完成？")) {
      return;
    }
    try {
      await markRectificationDone(itemId);
      setMessage("整改项已标记完成。");
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "标记整改失败");
    }
  }

  async function handleUndo(itemId: number) {
    if (!confirmRectificationAction("确认撤销该整改项的完成标记？")) {
      return;
    }
    try {
      await undoRectificationDone(itemId);
      setMessage("整改完成标记已撤销。");
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "撤销失败");
    }
  }

  async function handleCloseFollowup(itemId: number) {
    if (!confirmRectificationAction("确认将该待跟进项标记为已落实？")) {
      return;
    }
    try {
      await closeFollowup(itemId);
      setMessage("待跟进项已落实。");
      await refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "关闭待跟进失败");
    }
  }

  async function handleTriggerRecheck() {
    if (!taskId) {
      setMessage("请先输入任务 ID。");
      return;
    }
    if (!confirmRecheckAction(`确认触发任务 ${taskId} 的复查？\n\n系统将创建下一轮，只复查上一轮不满足项。`)) {
      return;
    }
    try {
      const result = await triggerRecheck(Number(taskId));
      setMessage(`复查已触发，新轮次：${String(result.new_round_no || "")}。复查已触发，可返回点检页执行新轮次。`);
      await refresh(taskId);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "触发复查失败");
    }
  }

  function confirmRectificationAction(message: string) {
    return window.confirm(message);
  }

  function confirmRecheckAction(message: string) {
    return window.confirm(message);
  }

  const allDone = rectifications.length > 0 && rectifications.every((item) => item.marked_done_at);

  return (
    <main className="page">
      <header className="page-header">
        <p className="eyebrow">整改</p>
        <h1>整改与复查</h1>
      </header>
      {message ? <p className="notice">{message}</p> : null}
      <section className="two-column">
        <form className="form-panel" onSubmit={handleSearch}>
          <h2>整改项</h2>
          <label>
            任务 ID
            <input name="task_id" value={taskId} onChange={(event) => setTaskId(event.target.value)} />
          </label>
          <button type="submit">查询整改项</button>
        </form>
        <section className="module">
          <h2>触发复查</h2>
          <p>所有整改项完成后，创建下一轮，只复查上一轮不满足项。</p>
          <button type="button" disabled={!allDone} onClick={handleTriggerRecheck}>
            触发复查
          </button>
        </section>
      </section>
      <section className="two-column spaced">
        <section className="module">
          <h2>整改清单</h2>
          <table>
            <thead>
              <tr>
                <th>检查项</th>
                <th>责任人</th>
                <th>计划完成</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {rectifications.map((item) => (
                <tr key={item.id}>
                  <td>{item.item_name_snapshot}</td>
                  <td>{item.responsible_owner}</td>
                  <td>{item.planned_finish_date}</td>
                  <td>
                    {item.marked_done_at ? (
                      <button className="secondary-button" type="button" onClick={() => void handleUndo(item.id)}>
                        撤销
                      </button>
                    ) : (
                      <button type="button" onClick={() => void handleMarkDone(item.id)}>
                        标记完成
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
        <section className="module">
          <h2>待跟进项</h2>
          <table>
            <thead>
              <tr>
                <th>检查项</th>
                <th>责任人</th>
                <th>计划完成</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {followups.map((item) => (
                <tr key={item.id}>
                  <td>{item.item_name_snapshot}</td>
                  <td>{item.responsible_owner}</td>
                  <td>{item.planned_finish_date}</td>
                  <td>
                    {item.closed_at ? (
                      "已落实"
                    ) : (
                      <button type="button" onClick={() => void handleCloseFollowup(item.id)}>
                        标记落实
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </section>
    </main>
  );
}
