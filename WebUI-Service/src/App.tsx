import { AnimatePresence, motion } from "framer-motion";
import { useState } from "react";
import { ChatTab } from "./components/ChatTab";
import { PlaceholderTab } from "./components/PlaceholderTab";
import { Sidebar, type TabId } from "./components/Sidebar";
import { SubmitTab } from "./components/SubmitTab";
import { useConversations } from "./hooks/useConversations";
import "./styles.css";

const PAGE_TITLES: Record<TabId, { title: string; subtitle: string }> = {
  chat: {
    title: "Club assistant",
    subtitle: "Local Ollama chat for AthleteCare orientation",
  },
  submit: {
    title: "Submit injury report",
    subtitle: "Send a clinical report into the n8n triage pipeline",
  },
  "staff-hub": {
    title: "Staff Hub",
    subtitle: "Club staff directory and roles",
  },
  "squad-status": {
    title: "Squad Status",
    subtitle: "Player availability and injury overview",
  },
  "knowledge-base": {
    title: "Knowledge Base",
    subtitle: "Clinical protocols and club guidance",
  },
  "match-schedule": {
    title: "Match Schedule",
    subtitle: "Fixtures and match-day planning",
  },
  "analytics-reports": {
    title: "Analytics & Reports",
    subtitle: "Triage trends and squad insights",
  },
};

function renderTabContent(
  tab: TabId,
  props: {
    activeTurns: ReturnType<typeof useConversations>["activeTurns"];
    appendTurn: ReturnType<typeof useConversations>["appendTurn"];
    homeResetToken: number;
    activeId: string | null;
  },
) {
  switch (tab) {
    case "chat":
      return (
        <ChatTab
          turns={props.activeTurns}
          onTurnAdd={(turn) => props.appendTurn(turn)}
          homeResetToken={props.homeResetToken}
          activeConversationId={props.activeId}
        />
      );
    case "submit":
      return <SubmitTab />;
    case "staff-hub":
      return (
        <PlaceholderTab
          title="Staff Hub"
          description="Staff directory, roles, and contact details will appear here."
        />
      );
    case "squad-status":
      return (
        <PlaceholderTab
          title="Squad Status"
          description="Player availability, injuries, and return-to-play status will appear here."
        />
      );
    case "knowledge-base":
      return (
        <PlaceholderTab
          title="Knowledge Base"
          description="Clinical protocols and club guidance documents will appear here."
        />
      );
    case "match-schedule":
      return (
        <PlaceholderTab
          title="Match Schedule"
          description="Fixtures, match days, and travel windows will appear here."
        />
      );
    case "analytics-reports":
      return (
        <PlaceholderTab
          title="Analytics & Reports"
          description="Triage trends, squad insights, and exportable reports will appear here."
        />
      );
    default:
      return null;
  }
}

export default function App() {
  const [tab, setTab] = useState<TabId>("chat");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [homeResetToken, setHomeResetToken] = useState(0);
  const {
    ready,
    conversations,
    activeId,
    activeTurns,
    goHome,
    selectConversation,
    appendTurn,
    deleteConversation,
    renameConversation,
  } = useConversations();

  const page = PAGE_TITLES[tab];

  function handleGoHome() {
    goHome();
    setTab("chat");
    setHomeResetToken((token) => token + 1);
  }

  return (
    <div className={`app-shell${sidebarCollapsed ? " sidebar-collapsed" : ""}`}>
      <Sidebar
        activeTab={tab}
        onTabChange={setTab}
        conversations={conversations}
        activeConversationId={activeId}
        onNewConversation={handleGoHome}
        onSelectConversation={(id) => void selectConversation(id)}
        onDeleteConversation={(id) => void deleteConversation(id)}
        onRenameConversation={(id, title) => void renameConversation(id, title)}
        onLogoClick={handleGoHome}
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed((c) => !c)}
      />

      <div className="main-area">
        <header className="main-header">
          <div className="page-header">
            <h1 className="page-title">{page.title}</h1>
            <p className="page-subtitle">{page.subtitle}</p>
          </div>
        </header>

        <main className="main-content">
          {!ready ? (
            <div className="panel loading-panel">
              <p className="lede">Loading conversation history…</p>
            </div>
          ) : (
            <AnimatePresence mode="wait">
              <motion.div
                key={tab}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.2 }}
                className="tab-view"
              >
                {renderTabContent(tab, {
                  activeTurns,
                  appendTurn,
                  homeResetToken,
                  activeId,
                })}
              </motion.div>
            </AnimatePresence>
          )}
        </main>
      </div>
    </div>
  );
}
