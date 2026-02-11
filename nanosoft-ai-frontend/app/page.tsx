"use client";

import { useState, useRef, useEffect } from "react";

// ─── Types ───────────────────────────────────────────────────────────────────
interface Message {
  role: "user" | "ai" | "error";
  text: string;
  // ✨ NEW: Optional array to hold file information in a message
  files?: { name: string; type: string }[];
}

interface ChatItem {
  id: string;
  title: string;
  preview: string;
}

interface FolderItem {
  id: string;
  name: string;
}

// ─── 1. Helper Code: Extract Text from Backend Response ─────────────────────
function extractText(raw: any, depth = 0): string {
  if (depth > 10 || raw == null) return "";
  if (typeof raw === "string") {
    const trimmed = raw.trim();
    if (trimmed.startsWith("{") || trimmed.startsWith("[")) {
      try {
        return extractText(JSON.parse(trimmed), depth + 1);
      } catch {
        return raw;
      }
    }
    return raw;
  }
  if (Array.isArray(raw)) {
    return raw
      .map((item) => extractText(item, depth + 1))
      .filter((text) => text.trim() !== "")
      .join(" ");
  }
  if (typeof raw === "object") {
    if (raw.response) return extractText(raw.response, depth + 1);
    if (raw.content) return extractText(raw.content, depth + 1);
    if (raw.text) return extractText(raw.text, depth + 1);
    if (raw.reply) return extractText(raw.reply, depth + 1);
    return "";
  }
  return String(raw);
}

// ─── Helper: Render Markdown to HTML (With Table Support) ───────────────────
function renderMarkdown(text: string, showCursor: boolean = false): string {
  if (!text) return "";

  const lines = text.split("\n");
  let html = "";
  let inList = false;
  let inOrderedList = false;
  let inTable = false;

  for (let i = 0; i < lines.length; i++) {
    let line = lines[i].trim();

    // ─── Table Logic ───
    if (line.startsWith("|") && line.endsWith("|")) {
      if (!inTable) {
        html += '<div style="overflow-x:auto; margin: 15px 0; border-radius: 8px; border: 1px solid rgba(59, 130, 246, 0.2); box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">';
        html += '<table style="width:100%; border-collapse: collapse; font-size: 13px; background: rgba(15, 23, 42, 0.6);">';
        inTable = true;
      }
      if (line.match(/^\|[\s-:|]+\|$/)) { continue; }

      const cells = line.split("|").filter((cell, index, arr) => index > 0 && index < arr.length - 1);
      const nextLine = lines[i + 1]?.trim();
      const isHeader = !html.includes("<thead>") && nextLine && nextLine.match(/^\|[\s-:|]+\|$/);

      if (isHeader) {
        html += '<thead><tr style="background: rgba(30, 41, 59, 0.8); border-bottom: 2px solid #3b82f6;">';
        cells.forEach(cell => {
          html += `<th style="padding: 12px 16px; text-align: left; font-weight: 600; color: #fff; border-right: 1px solid rgba(255,255,255,0.05);">${applyInline(cell.trim())}</th>`;
        });
        html += "</tr></thead><tbody>";
      } else {
        html += '<tr style="border-bottom: 1px solid rgba(255,255,255,0.05); transition: background 0.2s;">';
        cells.forEach(cell => {
          html += `<td style="padding: 10px 16px; color: #cbd5e1; border-right: 1px solid rgba(255,255,255,0.05);">${applyInline(cell.trim())}</td>`;
        });
        html += "</tr>";
      }
      continue;
    } else {
      if (inTable) { html += "</tbody></table></div>"; inTable = false; }
    }

    // ─── List/Text Logic ───
    const bulletMatch = line.match(/^[\s]*(?:\*\s+|-\s+|•\s+)(.*)/);
    const orderedMatch = line.match(/^[\s]*(\d+)[.)]\s+(.*)/);

    if (bulletMatch) {
      if (inOrderedList) { html += "</ol>"; inOrderedList = false; }
      if (!inList) { html += '<ul style="margin:10px 0 10px 20px;padding:0;list-style:disc;">'; inList = true; }
      html += `<li style="margin:5px 0;line-height:1.6;color:#dfe8df;">${applyInline(bulletMatch[1])}</li>`;
    } else if (orderedMatch) {
      if (inList) { html += "</ul>"; inList = false; }
      if (!inOrderedList) { html += '<ol style="margin:10px 0 10px 20px;padding:0;list-style:decimal;">'; inOrderedList = true; }
      html += `<li style="margin:5px 0;line-height:1.6;color:#dfe8df;">${applyInline(orderedMatch[2])}</li>`;
    } else {
      if (inList) { html += "</ul>"; inList = false; }
      if (inOrderedList) { html += "</ol>"; inOrderedList = false; }
      if (line.trim() === "") {
        html += '<div style="height:10px;"></div>';
      } else {
        html += `<div style="line-height:1.7;margin:2px 0;color:#dfe8df;">${applyInline(line)}</div>`;
      }
    }
  }
  
  if (inTable) html += "</tbody></table></div>";
  if (inList) html += "</ul>";
  if (inOrderedList) html += "</ol>";

  if (showCursor) {
    const cursorHtml = '<span style="display:inline-block;width:7px;height:16px;margin-left:4px;background:#3b82f6;border-radius:2px;vertical-align:middle;animation:blink 1s step-end infinite;"></span>';
    const lastClose = html.lastIndexOf("</");
    if (lastClose !== -1) {
      html = html.substring(0, lastClose) + cursorHtml + html.substring(lastClose);
    } else {
      html += cursorHtml;
    }
  }

  return html;
}

function generateSessionId() {
  return "session_" + Math.random().toString(36).substr(2, 9);
}

function applyInline(text: string): string {
  text = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  text = text.replace(/`([^`]+)`/g, '<code style="background:rgba(255,255,255,0.1);padding:2px 6px;border-radius:4px;font-family:monospace;font-size:13px;color:#a8e6cf;">$1</code>');
  text = text.replace(/\*\*(.+?)\*\*/g, '<strong style="color:#fff;font-weight:600;">$1</strong>');
  text = text.replace(/\*(.+?)\*/g, '<em style="color:#b0d4b8;font-style:italic;">$1</em>');
  return text;
}

// ─── Static Data ─────────────────────────────────────────────────────────────
const FOLDERS: FolderItem[] = [
  { id: "f1", name: "Work chats" },
  { id: "f2", name: "Life chats" },
  { id: "f3", name: "Projects chats" },
  { id: "f4", name: "Clients chats" },
];

const CHATS: ChatItem[] = [
  { id: "c1", title: "Plan a 3-day trip", preview: "It's a plan to the northern lights in Norway..." },
  { id: "c2", title: "Ideas for a customer loyalty program", preview: "Here are some ideas for a customer loyalty..." },
  { id: "c3", title: "Help me write", preview: "Here are some gift ideas for your upcoming..." },
];

const CATEGORIES = ["Text", "Image", "Video", "Audio", "Analytics"];

// ─── Icons ───────────────────────────────────────────────────────────────────
const IconFolder = () => <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z" /></svg>;
const IconChat = () => <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" /></svg>;
const IconPlus = () => <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><path d="M12 5v14M5 12h14" /></svg>;
const IconSearch = () => <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8" /><path d="M21 21l-4.35-4.35" /></svg>;
const IconDots = () => <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="5" r="1.5" /><circle cx="12" cy="12" r="1.5" /><circle cx="12" cy="19" r="1.5" /></svg>;
const IconBot = () => (<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 8V4H8" /><rect width="16" height="12" x="4" y="8" rx="2" /><path d="M2 14h2" /><path d="M20 14h2" /><path d="M15 13v2" /><path d="M9 13v2" /></svg>);
const IconAttach = () => <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21.44 11.05l-9.19 9.19a4.5 4.5 0 01-6.36-6.36l9.19-9.19a3 3 0 014.24 4.24l-9.2 9.19a1.5 1.5 0 01-2.12-2.12l8.49-8.48" /></svg>;
const IconSend = () => <svg width="16" height="16" viewBox="0 0 24 24" fill="white" stroke="none"><path d="M22 2L11 13" stroke="white" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" /><path d="M22 2L15 22L11 13L2 9L22 2Z" fill="white" /></svg>;
const IconMic = ({ isActive }: { isActive: boolean }) => <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={isActive ? "#3b82f6" : "currentColor"} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" fill={isActive ? "#3b82f6" : "none"} /><path d="M19 10v2a7 7 0 0 1-14 0v-2" /><line x1="12" y1="19" x2="12" y2="23" /><line x1="8" y1="23" x2="16" y2="23" /></svg>;
// ✨ NEW: Close Icon for file preview
const IconClose = () => <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>;

// ─── Main Component ──────────────────────────────────────────────────────────
export default function Home() {
  const [input, setInput] = useState<string>("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  // ✨ NEW: State to hold selected files
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);

  const messagesEndRef = useRef<HTMLDivElement | null>(null);
  const isTypingRef = useRef<boolean>(false);
  const inputRef = useRef<HTMLInputElement>(null);
  // ✨ NEW: Ref for hidden input
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [sessionId, setSessionId] = useState<string>(() => generateSessionId());
  const [searchVal, setSearchVal] = useState("");
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [chatName, setChatName] = useState("");
  const [activeCategory, setActiveCategory] = useState<string | null>(null);

  const [isRecording, setIsRecording] = useState<boolean>(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);

  const handleNewChat = () => {
    setMessages([]);       
    setChatName("New Chat"); 
    setSessionId(generateSessionId()); 
    setSelectedFiles([]); // Clear files
  };

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, isLoading, selectedFiles.length]); 

  // ─── File Handling Functions ───────────────────────────────────────────────
  const handleAttachClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const newFiles = Array.from(e.target.files);
      setSelectedFiles((prev) => [...prev, ...newFiles]);
    }
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const removeFile = (indexToRemove: number) => {
    setSelectedFiles((prev) => prev.filter((_, index) => index !== indexToRemove));
  };

  // ─── OPTIMIZED: Audio Recording Logic ───
  const toggleRecording = async () => {
    if (isRecording) {
      // STOP RECORDING
      // This triggers the 'onstop' event defined below
      mediaRecorderRef.current?.stop();
      setIsRecording(false);
    } else {
      // START RECORDING
      try {
        // ⚡ Optimization 1: Request low-bandwidth audio (Mono, 16kHz)
        // This makes the file 50-80% smaller without any processing delay.
        const stream = await navigator.mediaDevices.getUserMedia({ 
          audio: { 
            channelCount: 1,      // Mono
            sampleRate: 16000,    // 16kHz
            echoCancellation: true 
          } 
        });

        // ⚡ Optimization 2: Use efficient WebM format
        const options = { mimeType: "audio/webm;codecs=opus" }; 
        const mediaRecorder = new MediaRecorder(stream, options);
        const chunks: Blob[] = [];

        // Collect audio data as it comes in
        mediaRecorder.ondataavailable = (e) => {
          if (e.data.size > 0) chunks.push(e.data);
        };
        
        // When stopped, package the file and add to preview
        mediaRecorder.onstop = () => {
          const audioBlob = new Blob(chunks, { type: "audio/webm" });
          
          // Create a File object (looks just like an uploaded file)
          const audioFile = new File([audioBlob], `voice_note_${Date.now()}.webm`, { type: "audio/webm" });
          
          // Add to the list so the user sees it in the "File Preview" area
          setSelectedFiles((prev) => [...prev, audioFile]);
          
          // Stop all audio tracks to release the microphone hardware
          stream.getTracks().forEach(track => track.stop());
        };

        mediaRecorder.start();
        mediaRecorderRef.current = mediaRecorder;
        setIsRecording(true);

      } catch (error: any) {
        // ⚡ BETTER ERROR HANDLING
        console.error("Microphone Error:", error);
        
        if (error.name === "NotFoundError" || error.name === "DevicesNotFoundError") {
          alert("No microphone found! Please connect a microphone and try again.");
        } else if (error.name === "NotAllowedError" || error.name === "PermissionDeniedError") {
          alert("Permission denied. Please allow microphone access in your browser settings.");
        } else {
          alert("Error accessing microphone: " + error.message);
        }
        
        setIsRecording(false);
      }
    }
  };

  // ─── Updated sendMessage Function ─────────────────────────────────────────
  // Accepts optional textOverride for the clickable cards
  const sendMessage = async (textOverride?: string) => {
    const textToSend = typeof textOverride === "string" ? textOverride : input;
    
    // ✨ NEW: Allow send if there are files even if text is empty
    const hasFiles = selectedFiles.length > 0;
    if ((!textToSend.trim() && !hasFiles) || isLoading) return;
    
    // ✨ NEW: Prepare file metadata for chat history display
    const fileDataForMsg = selectedFiles.map(f => ({ name: f.name, type: f.type }));

    // Add User Message
    setMessages((prev) => [...prev, { role: "user", text: textToSend, files: fileDataForMsg }]);
    
    if (!textOverride) setInput("");
    setSelectedFiles([]); // Clear selection after sending
    setIsLoading(true);

    try {
      // Note: We are still sending JSON for now. 
      // Backend update for FormData will come in the next phase.
      const response = await fetch("http://127.0.0.1:8001/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: textToSend }), 
      });

      if (!response.ok) throw new Error(`Server error: ${response.status}`);

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      if (!reader) throw new Error("No response body");

      setIsLoading(false);
      isTypingRef.current = false; // Show cursor
      setMessages((prev) => [...prev, { role: "ai", text: "" }]);

      let accumulatedText = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split("\n").filter(line => line.trim() !== "");

        for (const line of lines) {
          try {
            let jsonStr = line;
            if (line.startsWith("data: ")) {
              jsonStr = line.slice(6);
            }

            const textPart = extractText(JSON.parse(jsonStr));
            
            if (textPart) {
              accumulatedText += textPart;
              setMessages((prev) => {
                const updated = [...prev];
                const lastIndex = updated.length - 1;
                if (updated[lastIndex].role === "ai") {
                    updated[lastIndex] = { role: "ai", text: accumulatedText };
                }
                return updated;
              });
              await new Promise(resolve => setTimeout(resolve, 10));
            }
          } catch (e) {
            // Ignore partial/invalid chunks
          }
        }
      }

      isTypingRef.current = false;
    } catch (error) {
      console.error("Chat Error:", error);
      setMessages((prev) => [...prev, { role: "error", text: "❌ Connection failed. Check backend." }]);
      setIsLoading(false);
      isTypingRef.current = false;
    } finally {
      setTimeout(() => {
        inputRef.current?.focus();
      }, 50);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") sendMessage();
  };

  const isLanding = messages.length === 0;

  return (
    <div className="app-container">
      <div className="bg-gradient" />

      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <div className="brand-box">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="white"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="white" strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" /></svg>
            </div>
            <span style={{ fontSize: "14px", fontWeight: 600, color: "#fff" }}>NANOSOFT ASK AI</span>
          </div>
        </div>

        <div className="search-container">
          <div className="search-input-box">
            <IconSearch />
            <input type="text" placeholder="Search" value={searchVal} onChange={(e) => setSearchVal(e.target.value)} />
          </div>
        </div>

        <div className="sidebar-scroll">
          <div className="section-title">Folders</div>
          {FOLDERS.map((f) => (
            <div key={f.id} className="sidebar-item">
              <div className="content">
                <IconFolder />
                <span style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{f.name}</span>
              </div>
              <div className="dots-btn"><IconDots /></div>
            </div>
          ))}
          
          <div className="section-title mt">Chats</div>
          {CHATS.map((c) => (
            <div 
              key={c.id} 
              className={`sidebar-item ${activeChatId === c.id ? 'active' : ''}`}
              onClick={() => { setActiveChatId(c.id); setChatName(c.title); setMessages([]); setSelectedFiles([]); }} 
            >
              <div style={{ display: "flex", alignItems: "flex-start", gap: "7px", minWidth: 0, flex: 1 }}>
                <div style={{ color: "#3b82f6", marginTop: "1px", flexShrink: 0 }}><IconChat /></div>
                <div style={{ minWidth: 0 }}>
                  <div className="title" style={{ fontSize: "13px", fontWeight: 500, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{c.title}</div>
                  <div className="preview" style={{ fontSize: "11px", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{c.preview}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
        
        <div className="new-chat-container">
          <button className="new-chat-btn" onClick={handleNewChat}>
            New chat &nbsp;<IconPlus />
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <div className="main-content">
        
        {/* Header */}
        <div className="chat-header">
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <span style={{ fontSize: "15px", fontWeight: 600, color: "#fff" }}>{chatName || "Gemini"}</span>
            <span className="model-badge">Flash latest</span>
          </div>
        </div>

        {/* Chat Area */}
        <div className="chat-scroll-area">
          {isLanding && (
            <div className="landing-container">
              <div className="landing-card">
                <div style={{ marginBottom: "16px", display: "flex", justifyContent: "center" }}><IconBot /></div>
                <h1 style={{ fontSize: "24px", fontWeight: 700, color: "#fff", marginBottom: "10px" }}>How can I help you today?</h1>
                <p style={{ fontSize: "12px", color: "#6a7a6a", lineHeight: 1.6, maxWidth: "380px", margin: "0 auto 28px" }}>Start a conversation to search assets, manage complaints, or check work orders.</p>
                
                {/* Clickable Feature Cards */}
                <div className="feature-grid">
                  {[
                    { title: "Search Assets", desc: "Find equipment details.", prompt: "Show me a list of all assets" },
                    { title: "Work Orders", desc: "Check schedules.", prompt: "Show me pending work orders" },
                    { title: "Complaints", desc: "Track issues.", prompt: "What are the recent complaints?" }
                  ].map((card, i) => (
                    <div 
                      key={i} 
                      className="feature-card" 
                      onClick={() => sendMessage(card.prompt)}
                      style={{ cursor: "pointer" }}
                    >
                      <div style={{ fontSize: "12px", fontWeight: 600, color: "#e0e8e0", marginBottom: "5px" }}>{card.title}</div>
                      <div style={{ fontSize: "10px", color: "#5a6a5a" }}>{card.desc}</div>
                    </div>
                  ))}
                </div>

                <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "6px", flexWrap: "wrap" }}>
                  {CATEGORIES.map((cat) => (
                    <button 
                      key={cat} 
                      className={`cat-pill ${activeCategory === cat ? 'active' : ''}`}
                      onClick={() => setActiveCategory(activeCategory === cat ? null : cat)}
                    >
                      {cat}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {!isLanding && (
            <div className="messages-container">
              {messages.map((msg, index) => {
                const isUser = msg.role === "user";
                const isError = msg.role === "error";
                const isLastAi = msg.role === "ai" && index === messages.length - 1;
                const showCursor = isLastAi && isTypingRef.current;

                return (
                  <div key={index} className={`message-row ${msg.role}`}>
                    {!isUser && !isError && (
                      <div className="avatar-box">
                        <IconBot />
                      </div>
                    )}

                    <div className={`message-bubble ${msg.role}`}>
                      {/* ✨ NEW: Display attached files tags */}
                      {msg.files && msg.files.length > 0 && (
                        <div style={{ marginBottom: "8px", display: "flex", flexWrap: "wrap", gap: "4px" }}>
                          {msg.files.map((f, fIdx) => (
                            <div key={fIdx} style={{ fontSize: "11px", background: "rgba(255,255,255,0.1)", padding: "4px 8px", borderRadius: "4px", display: "flex", alignItems: "center", gap: "4px" }}>
                              <IconAttach /> <span>{f.name}</span>
                            </div>
                          ))}
                        </div>
                      )}
                      
                      {(isUser || isError) ? (
                        <>{msg.text}</>
                      ) : (
                        <div className="ai-bubble">
                          <div dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.text, showCursor) }} />
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}

              {isLoading && (
                <div className="loading-indicator">
                  <div className="avatar-box">
                    <IconBot />
                  </div>
                  <div className="loading-dots-box">
                    {[0, 1, 2].map((i) => <span key={i} style={{ display: "inline-block", width: "7px", height: "7px", borderRadius: "50%", background: "#3b82f6", animation: `bounce 1.2s ease-in-out ${i * 0.2}s infinite` }} />)}
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input Area */}
        <div className="input-footer">
          {/* Hidden File Input (Kept same) */}
          <input 
            type="file" 
            ref={fileInputRef} 
            style={{ display: "none" }} 
            multiple 
            accept="image/*,audio/*,video/*,.pdf,.doc,.docx,.txt,.xls,.xlsx"
            onChange={handleFileChange}
          />

          {/* ✨ CHANGED: input-wrapper is now a Column Stack */}
          <div 
            className={`input-wrapper ${selectedFiles.length > 0 ? 'has-files' : ''}`}
            style={{ flexDirection: "column", alignItems: "flex-start", padding: "12px" }}
          >
            
            {/* 1. File Preview Section (Now Inside the wrapper!) */}
            {selectedFiles.length > 0 && (
              <div style={{ display: "flex", flexWrap: "wrap", gap: "8px", marginBottom: "10px", width: "100%" }}>
                {selectedFiles.map((file, index) => (
                  <div key={index} style={{ background: "rgba(255,255,255,0.08)", padding: "4px 8px", borderRadius: "6px", fontSize: "11px", color: "#e2e8f0", display: "flex", alignItems: "center", gap: "6px", border: "1px solid rgba(255,255,255,0.1)" }}>
                     <span style={{ maxWidth: "120px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{file.name}</span>
                     <button onClick={() => removeFile(index)} style={{ background: "none", border: "none", cursor: "pointer", padding: "0", display: "flex", color: "#94a3b8" }}>
                       <IconClose />
                     </button>
                  </div>
                ))}
              </div>
            )}

            {/* 2. The Input Row (Model + Input + Icons) */}
            <div style={{ display: "flex", alignItems: "center", width: "100%", gap: "10px" }}>
              
              <div className="model-selector">
                <div style={{ width: "14px", height: "14px", borderRadius: "4px", background: "linear-gradient(135deg,#3b82f6,#16a34a)", display: "flex", alignItems: "center", justifyContent: "center" }}><svg width="8" height="8" viewBox="0 0 24 24" fill="white"><path d="M12 2L2 7l10 5 10-5-10-5z" stroke="white" strokeWidth="2" fill="none" strokeLinecap="round" /></svg></div>
                <span style={{ fontSize: "11px", color: "#4a71de", fontWeight: 600 }}>Bot</span>
              </div>
              
              <input 
                type="text" 
                ref={inputRef} 
                className="main-input" 
                value={input} 
                onChange={(e) => setInput(e.target.value)} 
                onKeyDown={handleKeyDown} 
                disabled={isLoading} 
                placeholder="Type your prompt here..." 
                style={{ flex: 1 }} // Ensures input takes up remaining space
              />
              
              {/* Icons Group */}
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <div className="icon-btn" onClick={handleAttachClick}><IconAttach /></div>
                
                <div className={`mic-btn ${isRecording ? "recording" : ""}`} onClick={toggleRecording}>
                  <IconMic isActive={isRecording} />
                  {isRecording && <span style={{ position: "absolute", top: "-2px", right: "-2px", width: "8px", height: "8px", background: "#ef4444", borderRadius: "50%", border: "1.5px solid rgba(18,30,20,0.85)", animation: "blink 1s ease-in-out infinite" }} />}
                </div>
                
                <button className="send-btn" onClick={() => sendMessage()} disabled={isLoading || (!input.trim() && selectedFiles.length === 0)}>
                  <IconSend />
                </button>
              </div>

            </div>
          </div>

          <p className="footer-disclaimer">AI can make mistakes. Consider checking important information.</p>
        </div>
      </div>
    </div>
  );
}