import React, { useState, useEffect, useReducer } from 'react';
import { Box, Text, useInput, useApp } from 'ink';
import WebSocket from 'ws';
import LogView from './components/LogView.js';
import UserInput from './components/UserInput.js';
import StatusBar from './components/StatusBar.js';
import TodoDrawer from './components/TodoDrawer.js';

// Message type
interface Message {
  type: string;
  content: string;
  timestamp: Date;
}

// Task type
interface Task {
  id: string;
  text: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
}

// State type
interface AppState {
  messages: Message[];
  currentPlan: Task[];
  status: 'idle' | 'thinking' | 'executing' | 'error';
  statusText: string;
  todoVisible: boolean;
  connected: boolean;
  inputEnabled: boolean;
}

// Action types
type Action =
  | { type: 'ADD_MESSAGE'; message: Message }
  | { type: 'SET_PLAN'; tasks: Task[] }
  | { type: 'SET_STATUS'; status: AppState['status']; text?: string }
  | { type: 'TOGGLE_TODO' }
  | { type: 'SET_CONNECTED'; connected: boolean }
  | { type: 'SET_INPUT_ENABLED'; enabled: boolean };

// Reducer
function appReducer(state: AppState, action: Action): AppState {
  switch (action.type) {
    case 'ADD_MESSAGE':
      return {
        ...state,
        messages: [...state.messages, action.message]
      };
    
    case 'SET_PLAN':
      return {
        ...state,
        currentPlan: action.tasks
      };
    
    case 'SET_STATUS':
      return {
        ...state,
        status: action.status,
        statusText: action.text || action.status,
        inputEnabled: action.status === 'idle'
      };
    
    case 'TOGGLE_TODO':
      return {
        ...state,
        todoVisible: !state.todoVisible
      };
    
    case 'SET_CONNECTED':
      return {
        ...state,
        connected: action.connected
      };
    
    case 'SET_INPUT_ENABLED':
      return {
        ...state,
        inputEnabled: action.enabled
      };
    
    default:
      return state;
  }
}

// Initial state
const initialState: AppState = {
  messages: [],
  currentPlan: [],
  status: 'idle',
  statusText: 'Connecting...',
  todoVisible: false,
  connected: false,
  inputEnabled: false
};

// Banner
const BANNER = `
    █████╗   ███████╗   ██╗   ██╗   ██╗       
   ██╔══██╗   ╚════██╗  ██║   ██║   ██║      
  ███████║    █████╔╝   ██║   ██║   ██║       
 ██╔══██║    ██╔═══╝    ██║   ██║   ██║       
██║  ██║     ███████╗   ╚██████╔╝   ███████╗  
╚═╝  ╚═╝     ╚══════╝    ╚═════╝    ╚══════╝ 
`;

const App: React.FC = () => {
  const [state, dispatch] = useReducer(appReducer, initialState);
  const [ws, setWs] = useState<WebSocket | null>(null);
  const { exit } = useApp();
  
  // WebSocket connection
  useEffect(() => {
    const websocket = new WebSocket('ws://localhost:8765');
    
    websocket.on('open', () => {
      dispatch({ type: 'SET_CONNECTED', connected: true });
      dispatch({ type: 'SET_STATUS', status: 'idle', text: 'Ready' });
      dispatch({
        type: 'ADD_MESSAGE',
        message: {
          type: 'system',
          content: 'Connected to AZUL agent',
          timestamp: new Date()
        }
      });
    });
    
    websocket.on('message', (data: Buffer) => {
      try {
        const message = JSON.parse(data.toString());
        handleServerMessage(message);
      } catch (error) {
        console.error('Error parsing message:', error);
      }
    });
    
    websocket.on('error', (error) => {
      dispatch({
        type: 'ADD_MESSAGE',
        message: {
          type: 'error',
          content: `WebSocket error: ${error.message}`,
          timestamp: new Date()
        }
      });
    });
    
    websocket.on('close', () => {
      dispatch({ type: 'SET_CONNECTED', connected: false });
      dispatch({ type: 'SET_STATUS', status: 'error', text: 'Disconnected' });
    });
    
    setWs(websocket);
    
    return () => {
      websocket.close();
    };
  }, []);
  
  // Handle server messages
  const handleServerMessage = (message: any) => {
    switch (message.type) {
      case 'agent_thought':
        dispatch({
          type: 'ADD_MESSAGE',
          message: {
            type: 'thought',
            content: message.text,
            timestamp: new Date()
          }
        });
        break;
      
      case 'agent_plan':
        dispatch({ type: 'SET_PLAN', tasks: message.tasks });
        dispatch({
          type: 'ADD_MESSAGE',
          message: {
            type: 'plan',
            content: `Plan created with ${message.tasks.length} tasks`,
            timestamp: new Date()
          }
        });
        break;
      
      case 'tool_call':
        dispatch({
          type: 'ADD_MESSAGE',
          message: {
            type: 'tool_call',
            content: `⚡ ${message.tool}(${JSON.stringify(message.args)})`,
            timestamp: new Date()
          }
        });
        break;
      
      case 'tool_result':
        dispatch({
          type: 'ADD_MESSAGE',
          message: {
            type: message.success ? 'tool_result' : 'error',
            content: message.result,
            timestamp: new Date()
          }
        });
        break;
      
      case 'agent_response':
        dispatch({
          type: 'ADD_MESSAGE',
          message: {
            type: 'response',
            content: message.text,
            timestamp: new Date()
          }
        });
        break;
      
      case 'status_update':
        dispatch({
          type: 'SET_STATUS',
          status: message.status,
          text: message.text
        });
        break;
      
      case 'error':
        dispatch({
          type: 'ADD_MESSAGE',
          message: {
            type: 'error',
            content: `Error: ${message.error}${message.details ? ` - ${message.details}` : ''}`,
            timestamp: new Date()
          }
        });
        break;
    }
  };
  
  // Handle user input submission
  const handleSubmit = (input: string) => {
    if (!ws || !state.connected || !state.inputEnabled) {
      return;
    }
    
    // Add user message to log
    dispatch({
      type: 'ADD_MESSAGE',
      message: {
        type: 'user',
        content: input,
        timestamp: new Date()
      }
    });
    
    // Send to server
    ws.send(JSON.stringify({
      type: 'user_prompt',
      text: input
    }));
    
    // Disable input while processing
    dispatch({ type: 'SET_INPUT_ENABLED', enabled: false });
  };
  
  // Keyboard shortcuts
  useInput((input, key) => {
    if (key.ctrl && input === 't') {
      dispatch({ type: 'TOGGLE_TODO' });
    }
    
    if (key.ctrl && input === 'c') {
      exit();
    }
  });
  
  return (
    <Box flexDirection="column" height="100%">
      {/* Banner */}
      <Box marginBottom={1}>
        <Text color="cyan">{BANNER}</Text>
      </Box>
      
      {/* Main content area */}
      <Box flexDirection="row" flexGrow={1}>
        {/* Log view */}
        <Box flexGrow={1} flexDirection="column">
          <LogView messages={state.messages} />
        </Box>
        
        {/* Todo drawer (conditionally shown) */}
        {state.todoVisible && (
          <Box width={40} borderStyle="single" borderColor="cyan" marginLeft={1}>
            <TodoDrawer tasks={state.currentPlan} />
          </Box>
        )}
      </Box>
      
      {/* Input area */}
      <Box marginTop={1}>
        <UserInput
          onSubmit={handleSubmit}
          enabled={state.inputEnabled}
          placeholder={state.connected ? "Ask AZUL..." : "Connecting..."}
        />
      </Box>
      
      {/* Status bar */}
      <Box marginTop={1}>
        <StatusBar
          status={state.status}
          statusText={state.statusText}
          todoVisible={state.todoVisible}
        />
      </Box>
    </Box>
  );
};

export default App;

