"use client";

import React, { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { IconBulb, IconX, IconDotsVertical, IconFolder, IconFolderPlus } from "@tabler/icons-react";



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
                  placeholder="Copenhagen Trip"
                  style={{
                    flex: 1, background: 'transparent', border: 'none', color: 'var(--color-text)',
                    fontSize: '0.95rem', outline: 'none'
                  }}
                />
              </div>
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
                  background: newGroupName ? 'var(--color-primary)' : 'var(--color-border)',
                  border: 'none', borderRadius: '10px',
                  padding: '12px 24px', color: newGroupName ? '#000' : 'var(--color-text-muted)',
                  fontWeight: 600, cursor: newGroupName ? 'pointer' : 'not-allowed',
                  fontSize: '0.875rem',
                  transition: 'background 0.2s, opacity 0.2s',
                  boxShadow: newGroupName ? '0 4px 12px rgba(var(--color-primary-rgb), 0.3)' : 'none'
                }}
                disabled={!newGroupName}
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
