"use client";

import { useState, useEffect } from "react";
import { IconChevronLeft, IconChevronRight, IconX } from "@tabler/icons-react";

interface WalkthroughSlide {
  id: number;
  imageSrc: string;
}

const WALKTHROUGH_SLIDES: WalkthroughSlide[] = [
  {
    id: 1,
    imageSrc: "/walkthrough/img1/image.png",
  },
  {
    id: 2,
    imageSrc: "/walkthrough/img2/image.png",
  },
  {
    id: 3,
    imageSrc: "/walkthrough/img3/image.png",
  },
  {
    id: 4,
    imageSrc: "/walkthrough/img4/image.png",
  },
];

export default function WalkthroughPopup() {
  const [currentSlide, setCurrentSlide] = useState(0);
  const [isOpen, setIsOpen] = useState(true);

  // Auto-advance slides every 3 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentSlide((prev) => {
        if (prev < WALKTHROUGH_SLIDES.length - 1) {
          return prev + 1;
        } else {
          return 0; // Loop back to first slide
        }
      });
    }, 3000);

    return () => clearInterval(interval);
  }, []);

  // Blur sidebar and background when modal is open
  useEffect(() => {
    const sidebar = document.querySelector('.sidebar-shell');
    const mainContent = document.querySelector('[role="main"]') || document.querySelector('main');
    
    if (isOpen) {
      if (sidebar) {
        (sidebar as HTMLElement).style.filter = "blur(6px)";
      }
      if (mainContent) {
        (mainContent as HTMLElement).style.filter = "blur(6px)";
      }
    } else {
      if (sidebar) {
        (sidebar as HTMLElement).style.filter = "none";
      }
      if (mainContent) {
        (mainContent as HTMLElement).style.filter = "none";
      }
    }

    return () => {
      if (sidebar) {
        (sidebar as HTMLElement).style.filter = "none";
      }
      if (mainContent) {
        (mainContent as HTMLElement).style.filter = "none";
      }
    };
  }, [isOpen]);

  const handleNext = () => {
    if (currentSlide < WALKTHROUGH_SLIDES.length - 1) {
      setCurrentSlide((prev) => prev + 1);
    } else {
      handleClose();
    }
  };

  const handlePrevious = () => {
    if (currentSlide > 0) {
      setCurrentSlide((prev) => prev - 1);
    }
  };

  const handleClose = () => {
    setIsOpen(false);
  };

  const slide = WALKTHROUGH_SLIDES[currentSlide];

  if (!isOpen) {
    return null;
  }

  return (
    <>
      {/* Overlay */}
      <div
        data-walkthrough-overlay="true"
        style={{
          position: "fixed",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: "rgba(0, 0, 0, 0.5)",
          zIndex: 99998,
          backdropFilter: "blur(8px)",
        }}
        onClick={handleClose}
      />

      {/* Modal */}
      <div
        style={{
          position: "fixed",
          top: "50%",
          left: "50%",
          transform: "translate(-50%, -50%)",
          zIndex: 99999,
          width: "90%",
          maxWidth: "600px",
          height: "auto",
          maxHeight: "80vh",
          backgroundColor: "var(--color-bg)",
          borderRadius: "16px",
          border: `1px solid var(--color-border)`,
          boxShadow: "0 20px 60px rgba(0, 0, 0, 0.3)",
          overflow: "hidden",
          display: "flex",
          flexDirection: "column",
        }}
      >
        {/* Header */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "12px 16px",
            borderBottom: `1px solid var(--color-border)`,
            backgroundColor: "var(--color-bg-alt)",
          }}
        >
          <span
            style={{
              fontSize: "14px",
              color: "var(--color-text-muted)",
              fontWeight: 600,
            }}
          >
            {currentSlide + 1} of {WALKTHROUGH_SLIDES.length}
          </span>
          <button
            onClick={handleClose}
            style={{
              background: "none",
              border: "none",
              cursor: "pointer",
              color: "var(--color-text-muted)",
              padding: "4px",
              display: "flex",
              alignItems: "center",
              transition: "color 0.2s ease",
            }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLElement).style.color = "var(--color-text)";
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLElement).style.color = "var(--color-text-muted)";
            }}
          >
            <IconX size={20} />
          </button>
        </div>

        {/* Content - Image Display */}
        <div
          style={{
            flex: 1,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            padding: "24px 16px",
            backgroundColor: "var(--color-bg)",
            minHeight: "380px",
            width: "100%",
            overflow: "hidden",
          }}
        >
          <img
            src={slide.imageSrc}
            alt={`Slide ${currentSlide + 1}`}
            style={{
              maxWidth: "90%",
              maxHeight: "400px",
              width: "auto",
              height: "auto",
              display: "block",
              borderRadius: "10px",
              border: `2px solid var(--color-primary)`,
              objectFit: "contain",
            }}
            onError={(e) => {
              console.log("Image failed to load:", slide.imageSrc);
              (e.target as HTMLImageElement).style.border = "2px solid red";
            }}
          />
        </div>

        {/* Footer - Navigation */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "12px",
            padding: "12px 16px",
            borderTop: `1px solid var(--color-border)`,
            backgroundColor: "var(--color-bg-alt)",
          }}
        >
          {/* Left - Previous Button */}
          <button
            onClick={handlePrevious}
            disabled={currentSlide === 0}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              width: "36px",
              height: "36px",
              borderRadius: "6px",
              border: `1px solid var(--color-border)`,
              backgroundColor: "transparent",
              color: currentSlide === 0 ? "var(--color-text-muted)" : "var(--color-text)",
              cursor: currentSlide === 0 ? "not-allowed" : "pointer",
              opacity: currentSlide === 0 ? 0.5 : 1,
              transition: "all 0.2s ease",
            }}
            onMouseEnter={(e) => {
              if (currentSlide > 0) {
                (e.currentTarget as HTMLElement).style.backgroundColor = "var(--color-primary-soft)";
                (e.currentTarget as HTMLElement).style.borderColor = "var(--color-primary)";
              }
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLElement).style.backgroundColor = "transparent";
              (e.currentTarget as HTMLElement).style.borderColor = "var(--color-border)";
            }}
          >
            <IconChevronLeft size={18} />
          </button>

          {/* Middle - Dot Indicators */}
          <div style={{ display: "flex", gap: "6px" }}>
            {WALKTHROUGH_SLIDES.map((_, idx) => (
              <button
                key={idx}
                onClick={() => setCurrentSlide(idx)}
                style={{
                  width: idx === currentSlide ? "24px" : "8px",
                  height: "8px",
                  borderRadius: "4px",
                  backgroundColor:
                    idx === currentSlide ? "var(--color-primary)" : "var(--color-border)",
                  border: "none",
                  cursor: "pointer",
                  transition: "all 0.2s ease",
                }}
                onMouseEnter={(e) => {
                  (e.currentTarget as HTMLElement).style.backgroundColor = "var(--color-primary)";
                }}
                onMouseLeave={(e) => {
                  if (idx !== currentSlide) {
                    (e.currentTarget as HTMLElement).style.backgroundColor = "var(--color-border)";
                  }
                }}
              />
            ))}
          </div>

          {/* Right - Next Button */}
          <button
            onClick={handleNext}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              width: "36px",
              height: "36px",
              borderRadius: "6px",
              border: "none",
              backgroundColor: "var(--color-primary)",
              color: "#1f2937",
              cursor: "pointer",
              transition: "all 0.2s ease",
            }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLElement).style.boxShadow = "0 4px 12px rgba(212, 175, 55, 0.3)";
              (e.currentTarget as HTMLElement).style.transform = "translateY(-1px)";
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLElement).style.boxShadow = "none";
              (e.currentTarget as HTMLElement).style.transform = "translateY(0)";
            }}
          >
            <IconChevronRight size={18} />
          </button>
        </div>
      </div>
    </>
  );
}
