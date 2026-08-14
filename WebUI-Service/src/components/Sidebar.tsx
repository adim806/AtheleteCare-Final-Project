import { useState } from "react";
import {
  Activity,
  BarChart3,
  BookOpen,
  CalendarDays,
  ChevronLeft,
  ClipboardList,
  MessageSquare,
  Pencil,
  Plus,
  UserCheck,
  Users,
  X,
  type LucideIcon,
} from "lucide-react";
import type { ConversationRow } from "../db/sqliteDb";
import { formatRelativeTime } from "../lib/formatDate";
import { ServiceStatusBar } from "./ServiceStatusBar";

export type TabId =
  | "chat"
  | "submit"
  | "staff-hub"
  | "squad-status"
  | "knowledge-base"
  | "match-schedule"
  | "analytics-reports";

type Category = {
  id: TabId;
  label: string;
  icon: LucideIcon;
};

type SidebarProps = {
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
  conversations: ConversationRow[];
  activeConversationId: string | null;
  onNewConversation: () => void;
  onSelectConversation: (id: string) => void;
  onDeleteConversation: (id: string) => void;
  onRenameConversation: (id: string, title: string) => void;
  onLogoClick: () => void;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
};

const CATEGORIES: Category[] = [
  { id: "chat", label: "Assistant", icon: MessageSquare },
  { id: "submit", label: "Submit report", icon: ClipboardList },
  { id: "staff-hub", label: "Staff Hub", icon: Users },
  { id: "squad-status", label: "Squad Status", icon: UserCheck },
  { id: "knowledge-base", label: "Knowledge Base", icon: BookOpen },
  { id: "match-schedule", label: "Match Schedule", icon: CalendarDays },
  { id: "analytics-reports", label: "Analytics & Reports", icon: BarChart3 },
];

export function Sidebar({
  activeTab,
  onTabChange,
  conversations,
  activeConversationId,
  onNewConversation,
  onSelectConversation,
  onDeleteConversation,
  onRenameConversation,
  onLogoClick,
  collapsed = false,
  onToggleCollapse,
}: SidebarProps) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");

  function startRename(conv: ConversationRow) {
    setEditingId(conv.id);
    setEditTitle(conv.title);
  }

  function commitRename(id: string) {
    if (editingId !== id) return;
    onRenameConversation(id, editTitle);
    setEditingId(null);
    setEditTitle("");
  }

  function cancelRename() {
    setEditingId(null);
    setEditTitle("");
  }

  return (
    <aside
      className={`sidebar${collapsed ? " collapsed" : ""}`}
      aria-label="Navigation"
      aria-expanded={!collapsed}
    >
      <div className="sidebar-inner">
        <div className="sidebar-top">
          <div className="sidebar-brand-row">
            <button
              type="button"
              className="sidebar-brand-btn"
              onClick={onLogoClick}
              aria-label="Go to home — Club assistant"
              title="Home"
            >
              <span className="sidebar-brand-icon" aria-hidden="true">
                <Activity size={18} strokeWidth={1.75} />
              </span>
              <div className="sidebar-brand-text">
                <span className="sidebar-logo">AthleteCare</span>
                <span className="sidebar-tagline">Club medical triage</span>
              </div>
            </button>

            {onToggleCollapse && (
              <button
                type="button"
                className="sidebar-toggle"
                onClick={onToggleCollapse}
                aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
                title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
              >
                <ChevronLeft size={15} className="sidebar-toggle-icon" aria-hidden="true" />
              </button>
            )}
          </div>

          <button
            type="button"
            className="sidebar-new-btn"
            onClick={onNewConversation}
            title="New conversation"
          >
            <Plus size={15} aria-hidden="true" />
            <span className="sidebar-fade-label">New conversation</span>
          </button>
        </div>

        <nav className="sidebar-section sidebar-categories" aria-label="Categories">
          <p className="sidebar-section-label">
            <span>Categories</span>
          </p>
          <ul className="sidebar-nav">
            {CATEGORIES.map((cat) => {
              const Icon = cat.icon;
              return (
                <li key={cat.id}>
                  <button
                    type="button"
                    className={`sidebar-nav-item${activeTab === cat.id ? " active" : ""}`}
                    onClick={() => onTabChange(cat.id)}
                    title={cat.label}
                  >
                    <span className="sidebar-nav-icon">
                      <Icon size={17} aria-hidden="true" />
                    </span>
                    <span className="sidebar-fade-label">{cat.label}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>

        <div className="sidebar-expandable">
          <div className="sidebar-section sidebar-history">
            <p className="sidebar-section-label">
              <span>History</span>
            </p>
            {conversations.length === 0 ? (
              <div className="sidebar-empty">
                <MessageSquare size={28} strokeWidth={1.5} opacity={0.4} aria-hidden="true" />
                <p>Start a conversation to see history here</p>
              </div>
            ) : (
              <ul className="sidebar-history-list">
                {conversations.map((conv) => (
                  <li key={conv.id} className="sidebar-history-item">
                    {editingId === conv.id ? (
                      <input
                        className="sidebar-rename-input"
                        value={editTitle}
                        onChange={(e) => setEditTitle(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            e.preventDefault();
                            commitRename(conv.id);
                          }
                          if (e.key === "Escape") {
                            e.preventDefault();
                            cancelRename();
                          }
                        }}
                        onBlur={() => commitRename(conv.id)}
                        aria-label="Rename conversation"
                        autoFocus
                      />
                    ) : (
                      <button
                        type="button"
                        className={`sidebar-history-btn${
                          activeConversationId === conv.id ? " active" : ""
                        }`}
                        onClick={() => {
                          onTabChange("chat");
                          onSelectConversation(conv.id);
                        }}
                        title={conv.title}
                      >
                        <span className="sidebar-history-title">{conv.title}</span>
                        <span className="sidebar-history-time">
                          {formatRelativeTime(conv.created_at)}
                        </span>
                      </button>
                    )}
                    <div className="sidebar-history-actions">
                      <button
                        type="button"
                        className="sidebar-history-rename"
                        onClick={() => startRename(conv)}
                        aria-label={`Rename ${conv.title}`}
                        title="Rename"
                      >
                        <Pencil size={14} aria-hidden="true" />
                      </button>
                      <button
                        type="button"
                        className="sidebar-history-delete"
                        onClick={() => onDeleteConversation(conv.id)}
                        aria-label={`Delete ${conv.title}`}
                        title="Delete"
                      >
                        <X size={14} aria-hidden="true" />
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <ServiceStatusBar />

          <footer className="sidebar-footer">
            <p className="sidebar-footer-text">AthleteCare · Decision support</p>
          </footer>
        </div>
      </div>
    </aside>
  );
}
