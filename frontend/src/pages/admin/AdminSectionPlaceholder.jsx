import React from 'react';
import { Sparkles, Clock } from 'lucide-react';

export default function AdminSectionPlaceholder({ title, icon: Icon, description }) {
  return (
    <div className="admin-section-container">
      <div className="admin-section-icon-bg">
        {Icon ? <Icon size={32} /> : <Sparkles size={32} />}
      </div>
      <span className="admin-section-tag">
        <Clock size={12} style={{ display: 'inline', marginRight: '4px', verticalAlign: '-1px' }} />
        Module Under Development
      </span>
      <h2 className="admin-section-heading">{title}</h2>
      <p className="admin-section-message">
        {description || `The ${title} administration module is part of the TARIKA Admin Portal foundation and will be built incrementally in subsequent steps.`}
      </p>
    </div>
  );
}
