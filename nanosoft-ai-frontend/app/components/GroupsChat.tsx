"use client";

import React, { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { IconBulb, IconX, IconDotsVertical, IconFolder, IconFolderPlus, IconChevronRight, IconChevronDown, IconPlus } from "@tabler/icons-react";



const IconChat = ({ size = 16, ...props }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    {...props}
  >
    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
  </svg>
);

const IconCalendar = ({ size = 16, ...props }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    {...props}
  >
    <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
    <line x1="16" y1="2" x2="16" y2="6" />
    <line x1="8" y1="2" x2="8" y2="6" />
    <line x1="3" y1="10" x2="21" y2="10" />
  </svg>
);

interface Group {
  id: string;
  name: string;
  description: string;
  chatCount: number;
  updatedAt: string;
}

export default function GroupsChat({ createGroupTrigger = 0, groups = [], onCreateGroup }: { createGroupTrigger?: number; groups?: Group[]; onCreateGroup: (name: string) => void }) {
  const [isCreateGroupModalOpen, setIsCreateGroupModalOpen] = useState(false);
  const [newGroupName, setNewGroupName] = useState("");

  const isDuplicate = groups.some(g => g.name.toLowerCase() === newGroupName.trim().toLowerCase());

  const isFirstMount = useRef(true);

  useEffect(() => {
    if (isFirstMount.current) {
      isFirstMount.current = false;
      return;
    }
    if (createGroupTrigger > 0) {
      setIsCreateGroupModalOpen(true);
    }
  }, [createGroupTrigger]);

  return (
    <div className="groups-container" style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>




      {isCreateGroupModalOpen && typeof window !== 'undefined' && createPortal(
        <div style={{
          position: 'fixed', inset: 0, zIndex: 9999,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          backgroundColor: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(12px)',
          animation: 'fadeIn 0.2s ease-out'
        }}>
          <div style={{
            background: 'var(--color-sidebar-bg)', padding: '28px', borderRadius: '24px',
            width: '90%', maxWidth: '480px', border: '1px solid var(--color-border)',
            boxShadow: '0 25px 50px -12px rgba(0,0,0,0.25), 0 0 0 1px rgba(0,0,0,0.05)',
            color: 'var(--color-text)',
            animation: 'scaleIn 0.2s ease-out'
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
              <h3 style={{ margin: 0, fontSize: '1.5rem', fontWeight: 700, letterSpacing: '-0.025em' }}>Create group</h3>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <button style={{ background: 'transparent', border: 'none', color: 'var(--color-text-muted)', cursor: 'pointer', padding: '8px', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <IconDotsVertical size={20} />
                </button>
                <button
                  onClick={() => setIsCreateGroupModalOpen(false)}
                  style={{ background: 'transparent', border: 'none', color: 'var(--color-text-muted)', cursor: 'pointer', padding: '8px', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                >
                  <IconX size={20} />
                </button>
              </div>
            </div>

            <div style={{ marginBottom: '20px' }}>
              <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: 600, color: 'var(--color-text-muted)', marginBottom: '8px' }}>Group name</label>
              <div style={{
                display: 'flex', alignItems: 'center', gap: '12px',
                background: 'var(--color-bg-alt)', padding: '14px 16px', borderRadius: '12px',
                border: '1px solid var(--color-border)',
                transition: 'border-color 0.2s, box-shadow 0.2s'
              }}>
                <IconFolder size={20} style={{ color: 'var(--color-text-muted)' }} />
                <input
                  value={newGroupName}
                  onChange={(e) => setNewGroupName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && newGroupName.trim() && !isDuplicate) {
                      onCreateGroup(newGroupName.trim());
                      setIsCreateGroupModalOpen(false);
                      setNewGroupName("");
                    }
                  }}
                  placeholder="Complaints"
                  style={{
                    flex: 1, background: 'transparent', border: 'none', color: 'var(--color-text)',
                    fontSize: '0.95rem', outline: 'none'
                  }}
                />
              </div>
              {isDuplicate && (
                <div style={{ color: '#ff4d4d', fontSize: '0.75rem', marginTop: '4px', paddingLeft: '4px' }}>
                  Folder name already exists
                </div>
              )}
            </div>

            <div style={{
              background: 'var(--color-primary-soft)', padding: '16px 20px', borderRadius: '16px',
              border: '1px solid rgba(var(--color-primary-rgb), 0.2)', marginBottom: '28px',
              display: 'flex', gap: '12px', alignItems: 'flex-start'
            }}>
              <IconBulb size={22} style={{ color: 'var(--color-primary)', flexShrink: 0, marginTop: '2px' }} />
              <p style={{ margin: 0, fontSize: '0.875rem', color: 'var(--color-text)', lineHeight: '1.6' }}>
                Groups keep chats, files, and custom instructions in one place. Use them for ongoing work, or just to keep things tidy.
              </p>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
              <button
                onClick={() => setIsCreateGroupModalOpen(false)}
                style={{
                  background: 'transparent', border: '1px solid var(--color-border)', borderRadius: '10px',
                  padding: '12px 24px', color: 'var(--color-text)',
                  fontWeight: 600, cursor: 'pointer', fontSize: '0.875rem',
                  transition: 'background 0.2s'
                }}
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  onCreateGroup(newGroupName);
                  setIsCreateGroupModalOpen(false);
                  setNewGroupName("");
                }}
                style={{
                  background: (newGroupName && !isDuplicate) ? 'var(--color-primary)' : 'var(--color-border)',
                  border: 'none', borderRadius: '10px',
                  padding: '12px 24px', color: (newGroupName && !isDuplicate) ? '#000' : 'var(--color-text-muted)',
                  fontWeight: 600, cursor: (newGroupName && !isDuplicate) ? 'pointer' : 'not-allowed',
                  fontSize: '0.875rem',
                  transition: 'background 0.2s, opacity 0.2s',
                  boxShadow: (newGroupName && !isDuplicate) ? '0 4px 12px rgba(var(--color-primary-rgb), 0.3)' : 'none'
                }}
                disabled={!newGroupName || isDuplicate}
              >
                Create group
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}

export function FolderListItem({
  group,
  selectedGroupName,
  groupActiveType,
  editingFolderId,
  editingFolderTitle,
  setEditingFolderId,
  setEditingFolderTitle,
  expandedGroups,
  setExpandedGroups,
  setActiveFeature,
  setSelectedGroupName,
  setGroupActiveType,
  setMessages,
  sessionId,
  setSessionId,
  generateSessionId,
  chatSessions,
  onRename,
  setChatSessions,
  onDelete,
}: {
  group: any;
  selectedGroupName: string | null;
  groupActiveType: string;
  editingFolderId: string | null;
  editingFolderTitle: string;
  setEditingFolderId: (id: string | null) => void;
  setEditingFolderTitle: (title: string) => void;
  expandedGroups: string[];
  setExpandedGroups: (prev: any) => void;
  setActiveFeature: (feat: "chat" | "groups" | "archived") => void;
  setSelectedGroupName: (name: string) => void;
  setGroupActiveType: (type: 'folder' | 'chat') => void;
  setMessages: (msgs: any) => void;
  sessionId: string;
  setSessionId: (id: string) => void;
  generateSessionId: () => string;
  chatSessions: any[];
  onRename: (oldName: string, newName: string) => void;
  setChatSessions: (prev: any) => void;
  onDelete: (folderName: string) => void;
}) {
  const [openGroupMenuId, setOpenGroupMenuId] = useState<string | null>(null);
  const [openAbove, setOpenAbove] = useState(false);
  const [showDeleteFolderModal, setShowDeleteFolderModal] = useState(false);
  const [folderToDelete, setFolderToDelete] = useState("");
  const menuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setOpenGroupMenuId(null);
      }
    };
    if (openGroupMenuId) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [openGroupMenuId]);

  return (
    <div
      className="sidebar-sub-item"
      style={{
        padding: '6px 12px',
        paddingLeft: '36px',
        fontSize: '13px',
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        color: selectedGroupName === group.name && groupActiveType === 'folder' ? 'var(--color-accent, #c8932a)' : 'var(--color-text-secondary)',
        background: selectedGroupName === group.name && groupActiveType === 'folder' ? 'rgba(218, 165, 32, 0.12)' : 'transparent',
        borderRadius: '8px',
        fontWeight: selectedGroupName === group.name && groupActiveType === 'folder' ? 600 : 400,
        transition: 'background 0.15s, color 0.15s',
      }}
      onClick={() => {
        setExpandedGroups((prev: string[]) =>
          prev.includes(group.name)
            ? prev.filter(g => g !== group.name)
            : [...prev, group.name]
        );
        setActiveFeature('groups');
        setSelectedGroupName(group.name);
        setGroupActiveType('chat');
        setMessages([]); // This makes isLanding true!

        // If we are ALREADY on an empty "New Chat" inside this folder, DO NOT jump!
        const isCurrentEmpty = chatSessions.some((s: any) => s.id === sessionId && s.group_name === group.name && s.title === "New Chat");
        if (isCurrentEmpty) {
          return;
        }

        const existingEmptyChat = chatSessions.find((s: any) => s.group_name === group.name && s.title === "New Chat");
        if (existingEmptyChat) {
          setSessionId(existingEmptyChat.id);
        } else {
          const newSessionId = generateSessionId();
          setSessionId(newSessionId);
          setChatSessions((prev: any) => {
            return [{
              id: newSessionId,
              title: "New Chat",
              createdAt: Date.now(),
              updatedAt: Date.now(),
              group_name: group.name,
            }, ...prev];
          });
        }
      }}
    >
      {expandedGroups.includes(group.name) ? (
        <IconChevronDown size={14} style={{ marginRight: 2 }} />
      ) : (
        <IconChevronRight size={14} style={{ marginRight: 2 }} />
      )}
      <IconFolder width={14} height={14} />
      {editingFolderId === group.id ? (
        <input
          ref={(el) => { if (el) el.focus(); }}
          value={editingFolderTitle}
          onChange={(e) => setEditingFolderTitle(e.target.value)}
          onBlur={() => setEditingFolderId(null)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              onRename(group.name, editingFolderTitle);
              setEditingFolderId(null);
            }
            if (e.key === "Escape") {
              setEditingFolderId(null);
              setEditingFolderTitle("");
            }
          }}
          onClick={(e) => e.stopPropagation()}
          style={{
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
            borderRadius: 4,
            padding: "2px 4px",
            border: "1px solid var(--color-border)",
            background: "var(--color-bg-alt)",
            color: "var(--color-text)",
            width: '100%',
            fontSize: '13px',
          }}
        />
      ) : (
        <span key={group.name} className="title-typing" style={{ flex: 1 }}>{group.name}</span>
      )}
      <div style={{ position: 'relative' }} ref={menuRef}>
        <button
          onClick={(e) => {
            e.stopPropagation();
            const rect = e.currentTarget.getBoundingClientRect();
            const viewportH = window.innerHeight;
            setOpenAbove(viewportH - rect.bottom < 150);
            setOpenGroupMenuId(openGroupMenuId === group.id ? null : group.id);
          }}
          style={{
            background: 'transparent',
            border: 'none',
            color: 'var(--color-text-secondary)',
            cursor: 'pointer',
            padding: '4px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderRadius: '4px',
          }}
        >
          <IconDotsVertical width={14} height={14} />
        </button>

        {openGroupMenuId === group.id && (
          <div style={{
            position: 'absolute',
            top: openAbove ? 'auto' : '100%',
            bottom: openAbove ? '100%' : 'auto',
            right: 0,
            background: 'var(--color-sidebar-bg, #1a1a1a)',
            border: '1px solid var(--color-border)',
            borderRadius: '8px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.2)',
            zIndex: 1000,
            width: '120px',
            animation: 'dropdownOpen 150ms ease-out',
            transformOrigin: openAbove ? 'bottom right' : 'top right',
          }}>
            <button
              onClick={(e) => {
                e.stopPropagation();
                setOpenGroupMenuId(null);
                setEditingFolderId(group.id);
                setEditingFolderTitle(group.name);
              }}
              style={{
                width: '100%',
                padding: '8px 12px',
                textAlign: 'left',
                background: 'transparent',
                border: 'none',
                color: 'var(--color-text)',
                fontSize: '12px',
                cursor: 'pointer',
                display: 'flex',
                gap: '8px',
                alignItems: 'center',
              }}
            >
              Rename
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation();
                setOpenGroupMenuId(null);
                setFolderToDelete(group.name);
                setShowDeleteFolderModal(true);
              }}
              style={{
                width: '100%',
                padding: '8px 12px',
                textAlign: 'left',
                background: 'transparent',
                border: 'none',
                color: '#ff4d4d',
                fontSize: '12px',
                cursor: 'pointer',
                display: 'flex',
                gap: '8px',
                alignItems: 'center',
              }}
            >
              Delete
            </button>
          </div>
        )}
      </div>

      {typeof document !== 'undefined' && showDeleteFolderModal && createPortal(
        <div
          className="modal-backdrop"
          onClick={() => { setShowDeleteFolderModal(false); setFolderToDelete(""); }}
        >
          <div
            className="confirm-delete-modal"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            style={{
              minWidth: '280px',
              maxWidth: '400px',
              padding: '24px',
              background: '#151515',
              border: '1px solid #d4af37', // Gold border
              borderRadius: '12px',
              boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
              fontFamily: 'monospace', // Monospace font
            }}
          >
            <h3 style={{ fontSize: '16px', margin: '0 0 12px 0', fontWeight: 'bold', color: '#fff' }}>Delete folder?</h3>
            <p style={{ fontSize: '13px', color: '#aaa', margin: '0 0 24px 0', lineHeight: '1.5' }}>This will delete folder "<strong>{folderToDelete}</strong>".</p>
            <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end' }}>
              <button
                className="btn btn-secondary"
                onClick={() => { setShowDeleteFolderModal(false); setFolderToDelete(""); }}
                style={{
                  padding: '8px 16px',
                  fontSize: '13px',
                  borderRadius: '8px',
                  background: 'transparent',
                  border: '1px solid #333',
                  color: '#fff',
                  cursor: 'pointer',
                  fontFamily: 'monospace',
                }}
              >
                Cancel
              </button>
              <button
                className="btn btn-danger"
                onClick={() => {
                  onDelete(folderToDelete);
                  setShowDeleteFolderModal(false);
                  setFolderToDelete("");
                }}
                style={{
                  padding: '8px 16px',
                  fontSize: '13px',
                  borderRadius: '8px',
                  background: '#ff5c5c',
                  color: '#fff',
                  border: 'none',
                  cursor: 'pointer',
                  fontFamily: 'monospace',
                }}
              >
                Delete
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}

export function ChatListItem({
  s,
  sessionId,
  groupActiveType,
  editingSessionId,
  editingTitle,
  setEditingTitle,
  setEditingSessionId,
  commitRename,
  handleRenameSession,
  switchSession,
  setActiveFeature,
  setSelectedGroupName,
  setGroupActiveType,
  group,
  onDeleteChat,
}: {
  s: any;
  sessionId: string;
  groupActiveType: string;
  editingSessionId: string | null;
  editingTitle: string;
  setEditingTitle: (title: string) => void;
  setEditingSessionId: (id: string | null) => void;
  commitRename: (id: string) => void;
  handleRenameSession: (id: string) => void;
  switchSession: (id: string) => void;
  setActiveFeature: (feat: "chat" | "groups" | "archived") => void;
  setSelectedGroupName: (name: string) => void;
  setGroupActiveType: (type: 'folder' | 'chat') => void;
  group: any;
  onDeleteChat: (id: string) => void;
}) {
  const [openChatMenuId, setOpenChatMenuId] = useState<string | null>(null);
  const [openAbove, setOpenAbove] = useState(false);
  const [showDeleteChatModal, setShowDeleteChatModal] = useState(false);
  const editingInputRef = useRef<HTMLInputElement | null>(null);
  const chatMenuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (chatMenuRef.current && !chatMenuRef.current.contains(event.target as Node)) {
        setOpenChatMenuId(null);
      }
    };
    if (openChatMenuId) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [openChatMenuId]);

  return (
    <div
      className={`sidebar-sub-item ${s.id === sessionId && groupActiveType === 'chat' ? "active" : ""}`}
      onClick={() => {
        switchSession(s.id);
        setActiveFeature('groups');
        setSelectedGroupName(group.name);
        setGroupActiveType('chat');
      }}
      style={{
        padding: '4px 12px',
        paddingLeft: '52px',
        fontSize: '12px',
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        color: s.id === sessionId && groupActiveType === 'chat' ? 'var(--color-accent, #c8932a)' : 'var(--color-text-secondary)',
        background: s.id === sessionId && groupActiveType === 'chat' ? 'rgba(218, 165, 32, 0.10)' : 'transparent',
        borderRadius: '8px',
        fontWeight: s.id === sessionId && groupActiveType === 'chat' ? 600 : 400,
        transition: 'background 0.15s, color 0.15s',
      }}
    >
      {s.isSpaceBooking ? (
        <IconCalendar size={12} style={{ color: 'var(--color-primary, #d4af37)' }} />
      ) : (
        <IconChat size={12} />
      )}
      {editingSessionId === s.id ? (
        <input
          ref={(el) => { editingInputRef.current = el; if (el) el.focus(); }}
          value={editingTitle}
          onChange={(e) => setEditingTitle(e.target.value)}
          onBlur={() => commitRename(s.id)}
          onKeyDown={(e) => {
            if (e.key === "Enter") { e.preventDefault(); commitRename(s.id); }
            if (e.key === "Escape") { setEditingSessionId(null); setEditingTitle(""); }
          }}
          onClick={(e) => e.stopPropagation()}
          style={{
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
            borderRadius: 4,
            padding: "2px 4px",
            border: "1px solid var(--color-border)",
            background: "var(--color-bg-alt)",
            color: "var(--color-text)",
            width: '100%',
            fontSize: '11px',
          }}
        />
      ) : (
        <span
          key={s.title}
          className="title-typing"
          style={{ flex: 1, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}
        >
          {s.title}
        </span>
      )}
      <div style={{ position: 'relative' }} ref={chatMenuRef}>
        <button
          onClick={(e) => {
            e.stopPropagation();
            const rect = e.currentTarget.getBoundingClientRect();
            const viewportH = window.innerHeight;
            setOpenAbove(viewportH - rect.bottom < 150);
            setOpenChatMenuId(openChatMenuId === s.id ? null : s.id);
          }}
          style={{
            background: 'transparent',
            border: 'none',
            color: 'var(--color-text-secondary)',
            cursor: 'pointer',
            padding: '2px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderRadius: '4px',
          }}
        >
          <IconDotsVertical width={12} height={12} />
        </button>

        {openChatMenuId === s.id && (
          <div style={{
            position: 'absolute',
            top: openAbove ? 'auto' : '100%',
            bottom: openAbove ? '100%' : 'auto',
            right: 0,
            background: 'var(--color-sidebar-bg, #1a1a1a)',
            border: '1px solid var(--color-border)',
            borderRadius: '8px',
            boxShadow: '0 4px 12px rgba(0,0,0,0.2)',
            zIndex: 1000,
            width: '120px',
            animation: 'dropdownOpen 150ms ease-out',
            transformOrigin: openAbove ? 'bottom right' : 'top right',
          }}>
            <button
              onClick={(e) => {
                e.stopPropagation();
                setOpenChatMenuId(null);
                handleRenameSession(s.id);
              }}
              style={{
                width: '100%',
                padding: '6px 10px',
                textAlign: 'left',
                background: 'transparent',
                border: 'none',
                color: 'var(--color-text)',
                fontSize: '11px',
                cursor: 'pointer',
                display: 'flex',
                gap: '6px',
                alignItems: 'center',
              }}
            >
              Rename
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation();
                setOpenChatMenuId(null);
                onDeleteChat(s.id);
              }}
              style={{
                width: '100%',
                padding: '6px 10px',
                textAlign: 'left',
                background: 'transparent',
                border: 'none',
                color: '#ff4d4d',
                fontSize: '11px',
                cursor: 'pointer',
                display: 'flex',
                gap: '6px',
                alignItems: 'center',
              }}
            >
              Delete
            </button>
          </div>
        )}
      </div>


    </div>
  );
}
