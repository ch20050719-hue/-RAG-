export default {
  common: { version: 'SINGLE-ROOM SMART HOME v1.0.0', ready: 'READY', newSession: 'NEW SESSION', settings: 'Settings' },
  auth: {
    username: 'Username', email: 'Email', password: 'Password', fullName: 'Full Name', login: 'Login', logout: 'Logout', register: 'Register',
    loggingIn: 'Logging in...', registering: 'Registering...', usernamePlaceholder: 'Enter username', emailPlaceholder: 'Enter email address',
    passwordPlaceholder: 'Enter password', fullNamePlaceholder: 'Enter your full name', passwordHint: 'Password must be at least 6 characters',
    noAccount: "Don't have an account? Register now", hasAccount: 'Already have an account? Login now',
    errors: { required: 'All fields are required', loginFailed: 'Login failed, please check your credentials', registerFailed: 'Registration failed, please try again later', passwordTooShort: 'Password must be at least 6 characters' },
  },
  sidebar: {
    logo: '> SINGLE-ROOM SMART HOME', newChat: 'NEW SESSION', database: 'DATABASE', connected: 'CONNECTED', disconnected: 'DISCONNECTED', model: 'MODEL', latency: 'LATENCY',
    recentChats: 'Recent Chats', knowledgeBase: 'KNOWLEDGE BASE', selectKnowledgeBase: 'Select Knowledge Base', selectKnowledgeBases: 'Select Knowledge Bases', knowledgeBaseName: 'Knowledge Base Name', description: 'Description', createKnowledgeBase: 'Create Knowledge Base', create: 'Create', cancel: 'Cancel', selectAll: 'Select All', deselectAll: 'Deselect All', knowledgeBasesSelected: '{count} selected', close: 'Close', noKnowledgeBases: 'No knowledge bases', documents: 'DOCUMENTS', totalStorage: 'TOTAL STORAGE', chunks: 'CHUNKS', vectorDB: 'VECTOR DB', systemMetrics: 'SYSTEM METRICS', uptime: 'UPTIME', sessionId: 'SESSION ID', waitingForInput: 'WAITING_FOR_INPUT', memoryUsage: 'MEMORY USAGE',
  },
  chat: {
    emptyState: { title: 'SINGLE-ROOM SMART HOME', subtitle: 'READY TO QUERY DEVICES OR RUN SCENARIOS' },
    input: { placeholder: 'Enter a home command...', disclaimer: 'Device controls are safety-checked.', status: 'SYSTEM READY', pressEnter: 'PRESS ENTER TO SEND' },
    loading: { scanning: 'Scanning devices...', querying: 'Retrieving home knowledge...', generating: 'Generating response...' },
    messages: { user: '[USER DIRECTIVE]', assistant: '[SMART HOME ASSISTANT]', sources: '[KNOWLEDGE SOURCES]', doc: 'DOC', confidence: 'CONFIDENCE' },
    error: { failedToConnect: 'Error: Failed to connect to server', noResponse: 'Error: Failed to generate a response. Please check the server connection.' },
  },
  upload: {
    title: 'Upload Home Knowledge', dropzone: 'Drag & drop files here or click to select', supportedFormats: 'Supported formats:', clear: 'Clear', button: 'Upload Document', uploading: 'Uploading', pleaseSelectKB: 'Please select a knowledge base first',
    status: { completed: 'Completed', failed: 'Upload failed', pending: 'Pending', parsing: 'Parsing', processing: 'Processing' }, info: { title: 'Knowledge processing flow:', parsing: 'Extract device and scenario knowledge', chunking: 'Split by semantic sections', embedding: 'Generate vector embeddings' },
  },
  search: { title: 'Home Knowledge Search', queryLabel: 'Search query', placeholder: 'Enter a device, environment, or safety rule...', button: 'Search', topKLabel: 'Top-K results', results: 'Results', score: 'Similarity', page: 'Page', noResults: 'No matching results found', initial: { title: 'Home Knowledge Search', subtitle: 'Search manuals, sensor guides, scenarios, and safety rules' } },
  documents: { title: 'Knowledge Documents', refresh: 'Refresh', loading: 'Loading', fetchError: 'Failed to fetch documents', size: 'File Size', type: 'File Type', uploaded: 'Uploaded', error: 'Error Message', status: { completed: 'Completed', failed: 'Failed', pending: 'Pending', parsing: 'Parsing' }, noDocuments: 'No Documents', noDocumentsSub: 'Please upload home knowledge first', confirmDelete: 'Are you sure you want to delete this document?', delete: 'Delete' },
  nav: { chat: 'Chat', upload: 'Upload', search: 'Search', documents: 'Documents', editProfile: 'Edit Profile' },
  date: { justNow: 'Just now', minutesAgo: '{count}m ago', hoursAgo: '{count}h ago', daysAgo: '{count}d ago' },
}
