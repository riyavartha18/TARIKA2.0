import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { 
  User, 
  Mail, 
  Phone, 
  Lock, 
  Eye, 
  EyeOff, 
  ArrowRight, 
  AlertCircle,
  CheckCircle2
} from 'lucide-react';
import '../styles/tarika.css';

export default function Signup() {
  const { register, isLoading } = useAuth();
  const navigate = useNavigate();

  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    document.title = 'Create Account — TARIKA';
    const originalBg = document.body.style.backgroundColor;
    document.body.style.backgroundColor = '#FAF7F5';
    return () => {
      document.body.style.backgroundColor = originalBg;
    };
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!fullName.trim()) {
      setError('Please enter your full name.');
      return;
    }

    if (!email.trim()) {
      setError('Please enter your email address.');
      return;
    }

    if (!password) {
      setError('Please enter a password.');
      return;
    }

    if (password.length < 6) {
      setError('Password must be at least 6 characters long.');
      return;
    }

    if (password !== confirmPassword) {
      setError('Passwords do not match. Please re-enter.');
      return;
    }

    // Strictly provisions a CUSTOMER account. No role parameter is accepted or sent.
    const result = await register({
      fullName: fullName.trim(),
      email: email.trim(),
      phone: phone.trim(),
      password,
    });

    if (result.success) {
      navigate('/customer', { replace: true });
    } else {
      setError(result.error || 'Failed to create your customer account.');
    }
  };

  return (
    <div className="tarika-auth-page">
      <div className="tarika-auth-container">
        {/* Left Side: Brand Context & Atelier Privileges */}
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
              <span>Client Registration</span>
            </div>

            <h1 className="tarika-auth-hero-title">
              Begin Your Bespoke Fashion Journey.
            </h1>

            <p className="tarika-auth-hero-desc">
              Create your personal client profile to unlock curated capsule collections, tailored fit recommendations, and express priority dispatch.
            </p>
          </div>

          {/* Client Privileges Checklist */}
          <div className="tarika-auth-checklist">
            <div className="tarika-auth-checklist-item">
              <CheckCircle2 size={19} color="#D8727E" style={{ flexShrink: 0 }} />
              <span>Curated runway capsules & private sale previews</span>
            </div>
            <div className="tarika-auth-checklist-item">
              <CheckCircle2 size={19} color="#D8727E" style={{ flexShrink: 0 }} />
              <span>Complimentary luxury packaging & express doorstep delivery</span>
            </div>
            <div className="tarika-auth-checklist-item">
              <CheckCircle2 size={19} color="#D8727E" style={{ flexShrink: 0 }} />
              <span>Personalized silhouette recommendations & size concierge</span>
            </div>
          </div>
        </div>

        {/* Right Side: Registration Form */}
        <div className="tarika-auth-form-side">
          <div className="tarika-auth-form-header">
            <h2 className="tarika-auth-form-title">
              Create Your Account
            </h2>
            <p className="tarika-auth-form-subtitle">
              Sign up as a valued client to get started
            </p>
          </div>

          {error && (
            <div className="tarika-auth-alert">
              <AlertCircle size={18} style={{ flexShrink: 0 }} />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit}>
            {/* Full Name */}
            <div className="tarika-form-group">
              <label className="tarika-form-label" htmlFor="signup-name">Full Name</label>
              <div className="tarika-input-wrap">
                <User size={18} className="tarika-input-icon" />
                <input
                  id="signup-name"
                  type="text"
                  className="tarika-input"
                  placeholder="Vihaan Mittal"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  disabled={isLoading}
                  autoComplete="name"
                />
              </div>
            </div>

            {/* Email Address */}
            <div className="tarika-form-group">
              <label className="tarika-form-label" htmlFor="signup-email">Email Address</label>
              <div className="tarika-input-wrap">
                <Mail size={18} className="tarika-input-icon" />
                <input
                  id="signup-email"
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

            {/* Phone Number */}
            <div className="tarika-form-group">
              <label className="tarika-form-label" htmlFor="signup-phone">Phone Number (Optional)</label>
              <div className="tarika-input-wrap">
                <Phone size={18} className="tarika-input-icon" />
                <input
                  id="signup-phone"
                  type="tel"
                  className="tarika-input"
                  placeholder="9876543210"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  disabled={isLoading}
                  autoComplete="tel"
                />
              </div>
            </div>

            {/* Password */}
            <div className="tarika-form-group">
              <label className="tarika-form-label" htmlFor="signup-password">Password</label>
              <div className="tarika-input-wrap">
                <Lock size={18} className="tarika-input-icon" />
                <input
                  id="signup-password"
                  type={showPassword ? 'text' : 'password'}
                  className="tarika-input"
                  placeholder="Minimum 6 characters"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={isLoading}
                  autoComplete="new-password"
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

            {/* Confirm Password */}
            <div className="tarika-form-group">
              <label className="tarika-form-label" htmlFor="signup-confirm-password">Confirm Password</label>
              <div className="tarika-input-wrap">
                <Lock size={18} className="tarika-input-icon" />
                <input
                  id="signup-confirm-password"
                  type={showConfirmPassword ? 'text' : 'password'}
                  className="tarika-input"
                  placeholder="Re-enter your password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  disabled={isLoading}
                  autoComplete="new-password"
                />
                <button
                  type="button"
                  className="tarika-password-toggle"
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  tabIndex={-1}
                  aria-label={showConfirmPassword ? 'Hide password' : 'Show password'}
                >
                  {showConfirmPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
            </div>

            {/* Create Account Button */}
            <button
              type="submit"
              className="tarika-btn-auth-primary"
              disabled={isLoading}
            >
              {isLoading ? (
                <>
                  <div className="tarika-auth-spinner" />
                  <span>Creating Account...</span>
                </>
              ) : (
                <>
                  <span>Create Customer Account</span>
                  <ArrowRight size={18} />
                </>
              )}
            </button>
          </form>

          {/* Switch to Login Link */}
          <div className="tarika-auth-footer">
            Already have an account?{' '}
            <Link
              to="/login"
              className="tarika-auth-link"
            >
              Sign In
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}

