"""Custom CSS styles for Web Console."""


def get_custom_css() -> str:
    """Return custom CSS for the Web Console."""
    return """
    <style>
    /* Main container */
    .main > div {
        padding: 0;
    }
    
    /* Chat container */
    .chat-container {
        max-width: 1200px;
        margin: 0 auto;
        padding: 1rem;
    }
    
    /* Chat messages */
    .stChatMessage {
        border-radius: 12px;
        margin: 8px 0;
        padding: 12px 16px;
        transition: all 0.2s ease;
    }
    
    .stChatMessage:hover {
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    
    /* User message styling */
    .user-message {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 12px 12px 0 12px;
    }
    
    /* Assistant message styling */
    .assistant-message {
        background: #f8f9fa;
        border-left: 4px solid #667eea;
        border-radius: 12px 12px 12px 0;
    }
    
    /* Dark mode adjustments */
    [data-theme="dark"] .assistant-message {
        background: #2d3748;
        border-left: 4px solid #9f7aea;
    }
    
    /* Code blocks */
    .stCodeBlock {
        border-radius: 8px;
        margin: 8px 0;
    }
    
    /* Markdown content */
    .stMarkdown {
        line-height: 1.6;
    }
    
    .stMarkdown h1,
    .stMarkdown h2,
    .stMarkdown h3 {
        margin-top: 1.5em;
        margin-bottom: 0.5em;
    }
    
    .stMarkdown p {
        margin-bottom: 1em;
    }
    
    /* Sidebar */
    .sidebar-content {
        padding: 1rem;
    }
    
    /* Session list */
    .session-item {
        padding: 8px 12px;
        margin: 4px 0;
        border-radius: 6px;
        cursor: pointer;
        transition: all 0.2s ease;
        border: 1px solid transparent;
    }
    
    .session-item:hover {
        background: rgba(102, 126, 234, 0.1);
        border-color: #667eea;
    }
    
    .session-item.active {
        background: rgba(102, 126, 234, 0.2);
        border-color: #667eea;
        font-weight: 600;
    }
    
    /* Subagent monitor */
    .subagent-card {
        background: #f8f9fa;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 12px;
        margin: 8px 0;
    }
    
    [data-theme="dark"] .subagent-card {
        background: #2d3748;
        border-color: #4a5568;
    }
    
    .subagent-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 8px;
    }
    
    .subagent-status {
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 0.8em;
        font-weight: 600;
    }
    
    .status-running {
        background: #c6f6d5;
        color: #22543d;
    }
    
    .status-completed {
        background: #bee3f8;
        color: #2a4365;
    }
    
    .status-failed {
        background: #fed7d7;
        color: #742a2a;
    }
    
    /* Progress bar */
    .progress-bar {
        width: 100%;
        height: 6px;
        background: #e2e8f0;
        border-radius: 3px;
        overflow: hidden;
        margin: 8px 0;
    }
    
    .progress-fill {
        height: 100%;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        transition: width 0.3s ease;
    }
    
    /* Input area */
    .stChatInput {
        border-radius: 12px;
        border: 2px solid #e2e8f0;
        transition: border-color 0.2s ease;
    }
    
    .stChatInput:focus {
        border-color: #667eea;
    }
    
    /* Buttons */
    .stButton > button {
        border-radius: 8px;
        padding: 8px 16px;
        transition: all 0.2s ease;
    }
    
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    
    /* Expander */
    .streamlit-expanderHeader {
        border-radius: 8px;
        padding: 8px 12px;
    }
    
    /* Metrics */
    .metric-card {
        background: white;
        border-radius: 8px;
        padding: 16px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        text-align: center;
    }
    
    [data-theme="dark"] .metric-card {
        background: #2d3748;
    }
    
    .metric-value {
        font-size: 2em;
        font-weight: 700;
        color: #667eea;
    }
    
    .metric-label {
        color: #718096;
        font-size: 0.9em;
        margin-top: 4px;
    }
    
    /* Scrollbar */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    
    ::-webkit-scrollbar-track {
        background: #f1f1f1;
        border-radius: 4px;
    }
    
    ::-webkit-scrollbar-thumb {
        background: #c1c1c1;
        border-radius: 4px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: #a1a1a1;
    }
    
    [data-theme="dark"] ::-webkit-scrollbar-track {
        background: #2d3748;
    }
    
    [data-theme="dark"] ::-webkit-scrollbar-thumb {
        background: #4a5568;
    }
    
    /* Animations */
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .chat-message-animate {
        animation: fadeIn 0.3s ease;
    }
    
    /* Thinking indicator */
    .thinking-dots {
        display: inline-flex;
        gap: 4px;
        padding: 8px 12px;
    }
    
    .thinking-dot {
        width: 8px;
        height: 8px;
        background: #667eea;
        border-radius: 50%;
        animation: bounce 1.4s infinite ease-in-out both;
    }
    
    .thinking-dot:nth-child(1) { animation-delay: -0.32s; }
    .thinking-dot:nth-child(2) { animation-delay: -0.16s; }
    
    @keyframes bounce {
        0%, 80%, 100% { transform: scale(0); }
        40% { transform: scale(1); }
    }
    </style>
    """


def get_theme_config(theme: str = "dark") -> dict:
    """Get Streamlit theme configuration."""
    if theme == "dark":
        return {
            "primaryColor": "#667eea",
            "backgroundColor": "#1a202c",
            "secondaryBackgroundColor": "#2d3748",
            "textColor": "#f7fafc",
            "font": "sans serif",
        }
    else:
        return {
            "primaryColor": "#667eea",
            "backgroundColor": "#ffffff",
            "secondaryBackgroundColor": "#f7fafc",
            "textColor": "#2d3748",
            "font": "sans serif",
        }
