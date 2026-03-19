"use client";

import { useState } from "react";
import { IconCheck, IconCrown } from "@tabler/icons-react";
import { useResponsive } from "@/app/hooks/useResponsive";
import { useTheme } from "@/app/components/useTheme";

interface Plan {
  id: string;
  name: string;
  tagline: string;
  price: {
    monthly: number;
    yearly: number;
  };
  description: string;
  cta: string;
  ctaStyle: "primary" | "secondary";
  features: string[];
  badge?: string;
  badgeColor?: string;
  highlight?: boolean;
}

const plans: Plan[] = [
  {
    id: "free",
    name: "Free",
    tagline: "Get started",
    price: {
      monthly: 0,
      yearly: 0,
    },
    description: "Perfect for exploring",
    cta: "Use NanoSoft for free",
    ctaStyle: "secondary",
    features: [
      "Chat with basic AI",
      "Access to standard tools",
      "Data visualization",
      "Limited requests per day",
      "Basic support",
      "+2 more features",
    ],
  },
  {
    id: "pro",
    name: "Pro",
    tagline: "Most popular",
    price: {
      monthly: 17,
      yearly: 170,
    },
    description: "Advanced research and analysis",
    cta: "Get Pro plan",
    ctaStyle: "primary",
    features: [
      "Unlimited chat messages",
      "Advanced AI capabilities",
      "Real-time data processing",
      "Priority request handling",
      "Custom integrations",
      "Email support",
      "+4 more features",
    ],
    highlight: true,
    badgeColor: "#d4af37",
  },
  {
    id: "max",
    name: "Max",
    tagline: "Enterprise power",
    price: {
      monthly: 100,
      yearly: 1000,
    },
    description: "Maximum limits and priority access",
    cta: "Get Max plan",
    ctaStyle: "primary",
    features: [
      "Everything in Pro, plus:",
      "4x more usage than Pro",
      "Early access to new features",
      "Highest output limits",
      "Priority support 24/7",
      "Dedicated account manager",
      "Custom API access",
    ],
  },
];

interface UpgradePlanProps {
  onManageAccountClick?: () => void;
  onPlanChange?: (planName: string) => void;
}

export default function UpgradePlan({ onManageAccountClick, onPlanChange }: UpgradePlanProps) {
  const responsive = useResponsive();
  const { theme } = useTheme();
  const [billingCycle, setBillingCycle] = useState<"monthly" | "yearly">("monthly");
  const [currentPlanId, setCurrentPlanId] = useState<string>("free");

  const handlePlanSelection = (planId: string) => {
    setCurrentPlanId(planId);
    const plan = plans.find(p => p.id === planId);
    if (plan && onPlanChange) {
      onPlanChange(plan.name);
    }
  };
  
  // Subscription dates (demo data - would come from backend in production)
  const subscriptionDates = {
    startDate: new Date(2026, 0, 15),
    endDate: new Date(2027, 0, 15),
  };

  const savings = Math.round((plans[1].price.yearly - plans[1].price.monthly * 12) / (plans[1].price.monthly * 12) * 100);

  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      width: "100%",
      height: "100%",
      minHeight: 0,
      background: "var(--color-bg)",
      color: "var(--color-text)",
    }}>
      {/* Header - Fixed */}
      <div style={{
        width: "100%",
        padding: responsive.isMobile ? "14px" : responsive.isTablet ? "20px" : "28px",
        paddingBottom: responsive.isMobile ? "10px" : "14px",
        boxSizing: "border-box",
        textAlign: "center",
        flexShrink: 0,
      }}>
        <h1 style={{
          fontSize: responsive.isMobile ? "20px" : responsive.isTablet ? "28px" : "36px",
          fontWeight: 700,
          color: "#f3f4f6",
          marginBottom: "6px",
          display: "none",
        }}>
          Choose Your Plan
        </h1>
        <p style={{
          fontSize: responsive.isMobile ? "11px" : responsive.isTablet ? "12px" : "14px",
          color: "var(--color-text-muted)",
          marginBottom: "14px",
        }}>
          Select the perfect plan for your research and analysis needs
        </p>

        {/* Billing Toggle */}
        <div style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: "12px",
          marginTop: "12px",
        }}>
          <span 
            style={{
              fontSize: "14px",
              color: billingCycle === "monthly" ? "var(--color-primary)" : "var(--color-text-muted)",
              fontWeight: billingCycle === "monthly" ? 600 : 400,
              cursor: "pointer",
              transition: "all 0.3s ease",
              userSelect: "none",
            }}
            onClick={(e) => {
              e.stopPropagation();
              setBillingCycle("monthly");
            }}
          >
            Monthly
          </span>

          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              setBillingCycle(billingCycle === "monthly" ? "yearly" : "monthly");
            }}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: billingCycle === "monthly" ? "flex-start" : "flex-end",
              width: "56px",
              height: "28px",
              padding: "2px",
              borderRadius: "14px",
              background: "var(--glass-bg)",
              border: "1.5px solid var(--color-primary)",
              cursor: "pointer",
              transition: "all 0.3s ease-in-out",
              boxShadow: "0 0 12px var(--color-focus-ring)",
            }}
          >
            <div style={{
              width: "22px",
              height: "22px",
              borderRadius: "50%",
              background: "linear-gradient(180deg, var(--color-primary-soft) 0%, var(--color-primary-strong) 35%, var(--color-primary) 65%, var(--color-primary-strong) 100%)",
              boxShadow: "0 0 8px var(--color-primary)",
              transition: "all 0.3s ease-in-out",
            }} />
          </button>

          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span 
              style={{
                fontSize: "14px",
                color: billingCycle === "yearly" ? "var(--color-primary)" : "var(--color-text-muted)",
                fontWeight: billingCycle === "yearly" ? 600 : 400,
                cursor: "pointer",
                transition: "all 0.3s ease",
                userSelect: "none",
              }}
              onClick={(e) => {
                e.stopPropagation();
                setBillingCycle("yearly");
              }}
            >
              Yearly
            </span>
            {billingCycle === "yearly" && (
              <span style={{
                fontSize: "12px",
                color: "var(--color-success)",
                background: "var(--color-primary-soft)",
                padding: "4px 8px",
                borderRadius: "4px",
                fontWeight: 600,
              }}>
                Save {savings}%
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Scrollable Plans Section */}
      <div 
        className="upgrade-plan-scroll-container"
        style={{
          width: "100%",
          padding: responsive.isMobile ? "14px" : responsive.isTablet ? "20px" : "28px",
          paddingTop: responsive.isMobile ? "10px" : responsive.isTablet ? "14px" : "14px",
          paddingBottom: responsive.isMobile ? "20px" : "28px",
          boxSizing: "border-box",
          flex: 1,
          minHeight: 0,
          overflowY: "scroll",
          overflowX: "hidden",
          WebkitOverflowScrolling: "touch",
          scrollBehavior: "smooth",
          position: "relative",
        }}>
        {/* Plans Grid */}
        <div style={{
          display: "grid",
          gridTemplateColumns: responsive.isMobile
            ? "1fr"
            : responsive.isTablet
            ? "1fr"
            : "repeat(3, 1fr)",
          gap: responsive.isMobile ? "12px" : responsive.isTablet ? "12px" : "16px",
          width: "100%",
        }}>
        {plans.map((plan) => (
          <div
            key={plan.id}
            style={{
              position: "relative",
              borderRadius: "16px",
              background: plan.highlight
                ? "var(--color-primary-soft)"
                : "var(--glass-bg)",
              border: plan.highlight
                ? "1.5px solid var(--color-primary)"
                : "1px solid var(--color-border)",
              padding: responsive.isMobile ? "16px" : responsive.isTablet ? "18px" : "22px",
              backdropFilter: "blur(12px)",
              transition: "all 0.3s ease",
              transform: plan.highlight ? (responsive.isMobile ? "none" : "scale(1.05)") : "scale(1)",
            }}
            onMouseEnter={(e) => {
              if (!plan.highlight && !responsive.isMobile) {
                (e.currentTarget as HTMLElement).style.borderColor = "var(--color-primary)";
                (e.currentTarget as HTMLElement).style.background = "var(--color-bg-active)";
              }
            }}
            onMouseLeave={(e) => {
              if (!plan.highlight && !responsive.isMobile) {
                (e.currentTarget as HTMLElement).style.borderColor = "var(--color-border)";
                (e.currentTarget as HTMLElement).style.background = "var(--glass-bg)";
              }
            }}
          >
            {/* Active Plan Indicator Dot */}
            {currentPlanId === plan.id && (
              <div style={{
                position: "absolute",
                top: "10px",
                left: "10px",
                width: "12px",
                height: "12px",
                borderRadius: "50%",
                background: "#22c55e",
                boxShadow: "0 0 6px rgba(34, 197, 94, 0.5)",
              }} />
            )}

            {/* Badge */}
            {plan.highlight && !responsive.isMobile && (
              <div style={{
                position: "absolute",
                top: "-12px",
                left: "50%",
                transform: "translateX(-50%)",
                background: "linear-gradient(180deg, var(--color-primary-soft) 0%, var(--color-primary-strong) 35%, var(--color-primary) 65%, var(--color-primary-strong) 100%)",
                color: "var(--color-text)",
                padding: "6px 16px",
                borderRadius: "20px",
                fontSize: "12px",
                fontWeight: 700,
                display: "flex",
                alignItems: "center",
                gap: "6px",
                boxShadow: "0 4px 12px var(--color-focus-ring)",
              }}>
                <IconCrown size={14} />
                {plan.tagline}
              </div>
            )}

            {/* Plan Header */}
            <div style={{ marginBottom: "16px" }}>
              {plan.highlight && responsive.isMobile && (
                <div style={{
                  fontSize: "11px",
                  fontWeight: 700,
                  color: "var(--color-primary)",
                  marginBottom: "6px",
                  textTransform: "uppercase",
                  letterSpacing: "0.5px",
                }}>
                  {plan.tagline}
                </div>
              )}
              <h3 style={{
                fontSize: responsive.isMobile ? "20px" : responsive.isTablet ? "22px" : "24px",
                fontWeight: 700,
                color: "var(--color-text)",
                marginBottom: "4px",
              }}>
                {plan.name}
              </h3>
              <p style={{
                fontSize: "12px",
                color: "var(--color-text-muted)",
                marginBottom: "8px",
              }}>
                {plan.description}
              </p>
              {currentPlanId === plan.id && (
                <p style={{
                  fontSize: "11px",
                  color: "var(--color-text-muted)",
                  marginTop: "6px",
                  paddingTop: "8px",
                  borderTopWidth: "1px",
                  borderTopStyle: "solid",
                  borderTopColor: "var(--color-border)",
                }}>
                  Active until {subscriptionDates.endDate.toLocaleDateString("en-US", { 
                    year: "numeric", 
                    month: "short", 
                    day: "numeric" 
                  })}
                </p>
              )}
            </div>

            {/* Pricing */}
            <div style={{
              marginBottom: "16px",
              paddingBottom: "16px",
              borderBottom: "1px solid var(--color-border)"
            }}>
              <div style={{
                display: "flex",
                alignItems: "baseline",
                gap: "6px",
                marginBottom: "2px",
              }}>
                <span style={{
                  fontSize: responsive.isMobile ? "28px" : responsive.isTablet ? "32px" : "36px",
                  fontWeight: 700,
                  color: plan.highlight ? "var(--color-primary)" : "var(--color-text)",
                }}>
                  ${billingCycle === "monthly" ? plan.price.monthly : Math.floor(plan.price.yearly / 12)}
                </span>
                <span style={{
                  fontSize: "12px",
                  color: "var(--color-text-muted)",
                }}>
                  USD / month
                </span>
              </div>
              {billingCycle === "yearly" && (
                <p style={{
                  fontSize: "12px",
                  color: "#6b7280",
                }}>
                  Billed ${plan.price.yearly} annually
                </p>
              )}
            </div>

            {/* CTA Button */}
            <button
              type="button"
              onClick={() => handlePlanSelection(plan.id)}
              style={{
                width: "100%",
                padding: "8px 12px",
                borderRadius: "6px",
                fontSize: "11px",
                fontWeight: 600,
                cursor: "pointer",
                transition: "all 0.3s ease",
                marginBottom: "14px",
                background: plan.ctaStyle === "primary"
                  ? "var(--color-primary)"
                  : "transparent",
                color: plan.ctaStyle === "primary" ? "var(--color-text)" : "var(--color-primary)",
                border: plan.ctaStyle === "primary" ? "none" : "1.5px solid var(--color-primary)",
                boxShadow: plan.ctaStyle === "primary"
                  ? "0 2px 8px rgba(212, 175, 55, 0.2)"
                  : "none",
              }}
              onMouseEnter={(e) => {
                const btn = e.currentTarget as HTMLElement;
                if (plan.ctaStyle === "primary") {
                  btn.style.boxShadow = "0 4px 12px rgba(212, 175, 55, 0.3)";
                  btn.style.transform = "translateY(-1px)";
                } else {
                  btn.style.background = "var(--color-primary-soft)";
                }
              }}
              onMouseLeave={(e) => {
                const btn = e.currentTarget as HTMLElement;
                if (plan.ctaStyle === "primary") {
                  btn.style.boxShadow = "0 2px 8px rgba(212, 175, 55, 0.2)";
                  btn.style.transform = "translateY(0)";
                } else {
                  btn.style.background = "transparent";
                }
              }}
            >
              {plan.cta}
            </button>

            {/* Features List */}
            <div style={{
              display: "flex",
              flexDirection: "column",
              gap: "8px",
            }}>
              {plan.features.map((feature, featureIdx) => (
                <div
                  key={featureIdx}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    fontSize: responsive.isMobile ? "11px" : responsive.isTablet ? "12px" : "13px",
                  }}
                >
                  {feature.startsWith("+") ? (
                    <div style={{
                      fontSize: "12px",
                      color: "var(--color-primary)",
                      fontWeight: 600,
                      minWidth: "16px",
                    }}>
                      +
                    </div>
                  ) : (
                    <IconCheck
                      size={18}
                      style={{
                        color: "var(--color-success)",
                        flexShrink: 0,
                      }}
                    />
                  )}
                  <span style={{
                    color: feature.startsWith("+") ? "var(--color-primary)" : "var(--color-text)",
                  }}>
                    {feature}
                  </span>
                </div>
              ))}
            </div>

            {/* Footer Note */}
            {plan.id === "max" && (
              <p style={{
                fontSize: "12px",
                color: "var(--color-text-muted)",
                marginTop: "16px",
                paddingTop: "16px",
                borderTop: "1px solid var(--color-border)",
              }}>
                No commitment • Cancel anytime
              </p>
            )}
          </div>
        ))}
        </div>
      </div>

      {/* Footer Note */}
      <div style={{
        width: "100%",
        padding: responsive.isMobile ? "14px" : responsive.isTablet ? "20px" : "28px",
        paddingTop: responsive.isMobile ? "10px" : "14px",
        boxSizing: "border-box",
        borderTop: "1px solid var(--color-border)",
        flexShrink: 0,
      }}>
        <p style={{
          textAlign: "center",
          fontSize: "11px",
          color: "#6b7280",
          margin: 0,
        }}>
          All prices are in USD. Prices do not include applicable taxes. Upgrade or downgrade your plan anytime.
        </p>
      </div>
    </div>
  );
}
