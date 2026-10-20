import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { 
  Mail, 
  Lock, 
  Eye, 
  EyeOff, 
  ArrowRight, 
  AlertCircle, 
  Sparkles
} from 'lucide-react';
import '../styles/tarika.css';

export default function Login() {
  const { login, isLoading } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    document.title = 'Sign In — TARIKA';
    const originalBg = document.body.style.backgroundColor;
    document.body.style.backgroundColor = '#FAF7F5';
    return () => {
      document.body.style.backgroundColor = originalBg;
    };
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!email.trim()) {
      setError('Please enter your email address.');
      return;
    }

    if (!password) {
      setError('Please enter your password.');
      return;
    }

    const result = await login(email.trim(), password);

    if (result.success) {
      navigate(result.redirectPath, { replace: true });
    } else {
      setError(result.error || 'Authentication failed. Please check your credentials.');
    }
  };

  return (
    <div className="tarika-auth-page">
      <div className="tarika-auth-container">
        {/* Left Side: TARIKA Haute Editorial Atelier */}
        <div className="tarika-auth-hero">
          {/* Subtle Ambient Glow */}
          <div className="tarika-auth-hero-glow" />

          <div>
            {/* Clickable Brand Logo linking to Homepage */}
            <Link
              to="/"
              style={{
                textDecoration: 'none',
                display: 'inline-flex',
                flexDirection: 'column',
                alignItems: 'flex-start',
                cursor: 'pointer',
                marginBottom: '2.5rem'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span
                  className="tarika-serif"
                  style={{
                    fontSize: '1.85rem',
                    fontWeight: 700,
                    letterSpacing: '0.22em',
                    color: '#1F191B',
                    lineHeight: 1.1
                  }}
                >
                  TARIKA
                </span>
              </div>
              <span
                style={{
                  fontSize: '0.62rem',
                  fontWeight: 600,
                  letterSpacing: '0.22em',
                  color: '#D8727E',
                  textTransform: 'uppercase',
                  marginTop: '0.2rem'
                }}
              >
                STYLE YOUR STORY
              </span>
            </Link>

            <div className="tarika-auth-brand-badge">
              <span>✦</span>
              <span>Haute Editorial Atelier</span>
            </div>

            <h1 className="tarika-auth-hero-title">
              Where Luxury Fashion Meets Your Everyday Story.
            </h1>

            <p className="tarika-auth-hero-desc">
              Sign in to access your curated boutique wardrobe, private styling consultations, personalized runway recommendations, and seamless concierge delivery.
            </p>
          </div>

          {/* Bottom Luxury Guarantee / Perk Card */}
          <div className="tarika-auth-perk-card">
            <div className="tarika-auth-perk-icon-wrap">
              <Sparkles size={22} />
            </div>
            <div>
              <p className="tarika-auth-perk-title">Seamless Client Access</p>
              <p className="tarika-auth-perk-sub">Personalized wardrobe curation, wishlists, and express checkout.</p>
            </div>
          </div>
        </div>

        {/* Right Side: Clean TARIKA Login Form */}
        <div className="tarika-auth-form-side">
          <div className="tarika-auth-form-header">
            <h2 className="tarika-auth-form-title">
              Welcome Back
            </h2>
            <p className="tarika-auth-form-subtitle">
              Sign in to your TARIKA account to continue
            </p>
          </div>

          {error && (
            <div className="tarika-auth-alert">
              <AlertCircle size={18} style={{ flexShrink: 0 }} />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit}>
            {/* Email Field */}
            <div className="tarika-form-group">
              <label className="tarika-form-label" htmlFor="login-email">Email Address</label>
              <div className="tarika-input-wrap">
                <Mail size={18} className="tarika-input-icon" />
                <input
                  id="login-email"
                  type="email"
                  className="tarika-input"
                  placeholder="name@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  disabled={isLoading}
                  autoComplete="email"
                />
              </div>
            </div>

            {/* Password Field */}
            <div className="tarika-form-group">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.45rem' }}>
                <label className="tarika-form-label" htmlFor="login-password" style={{ marginBottom: 0 }}>Password</label>
                <a
                  href="#forgot"
                  onClick={(e) => { e.preventDefault(); alert('Password recovery is managed via administrative support or Supabase reset flow.'); }}
                  style={{ fontSize: '0.8rem', color: '#D8727E', textDecoration: 'none', fontWeight: 600 }}
                  onMouseEnter={(e) => e.currentTarget.style.color = '#B8505E'}
                  onMouseLeave={(e) => e.currentTarget.style.color = '#D8727E'}
                >
                  Forgot password?
                </a>
              </div>
              <div className="tarika-input-wrap">
                <Lock size={18} className="tarika-input-icon" />
                <input
                  id="login-password"
                  type={showPassword ? 'text' : 'password'}
                  className="tarika-input"
                  placeholder="Enter your password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={isLoading}
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  className="tarika-password-toggle"
                  onClick={() => setShowPassword(!showPassword)}
                  tabIndex={-1}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              className="tarika-btn-auth-primary"
              disabled={isLoading}
            >
              {isLoading ? (
                <>
                  <div className="tarika-auth-spinner" />
                  <span>Signing in...</span>
                </>
              ) : (
                <>
                  <span>Sign In</span>
                  <ArrowRight size={18} />
                </>
              )}
            </button>
          </form>

          {/* Divider */}
          <div className="tarika-auth-divider">
            <div className="tarika-auth-divider-line" />
            <span className="tarika-auth-divider-text">or</span>
            <div className="tarika-auth-divider-line" />
          </div>

          {/* Google OAuth (UI Demo button) */}
          <button
            type="button"
            className="tarika-btn-auth-secondary"
            onClick={() => alert('Google OAuth provider is configured in Supabase Dashboard. Use customer email/password credentials for local testing.')}
          >
            <svg width="18" height="18" viewBox="0 0 24 24">
              <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
              <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
              <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" />
              <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" />
            </svg>
            <span>Continue with Google</span>
          </button>

          {/* Switch to Signup Link */}
          <div className="tarika-auth-footer">
            Don't have an account?{' '}
            <Link
              to="/signup"
              className="tarika-auth-link"
            >
              Create Account
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}

