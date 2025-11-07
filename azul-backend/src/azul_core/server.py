"""WebSocket server for AZUL backend."""

import asyncio
import json
import logging
from typing import Optional
import websockets
from websockets.server import WebSocketServerProtocol

from .agent import AzulAgent
from .protocol import (
    UserPromptMessage,
    AgentThoughtMessage,
    ToolCallMessage,
    ToolResultMessage,
    AgentResponseMessage,
    StatusUpdateMessage,
    ErrorMessage
)
from .config import config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AzulServer:
    """WebSocket server for AZUL agent."""
    
    def __init__(self, host: str = "localhost", port: int = 8765):
        """Initialize the server.
        
        Args:
            host: Host to bind to
            port: Port to listen on
        """
        self.host = host
        self.port = port
        self.agent: Optional[AzulAgent] = None
    
    async def handle_client(self, websocket: WebSocketServerProtocol):
        """Handle a client connection.
        
        Args:
            websocket: WebSocket connection
        """
        logger.info(f"Client connected from {websocket.remote_address}")
        
        # Create agent instance for this connection
        agent = AzulAgent(
            on_thought=lambda text: asyncio.create_task(
                self.send_message(websocket, AgentThoughtMessage(text=text))
            ),
            on_tool_call=lambda tool, args: asyncio.create_task(
                self.send_message(websocket, ToolCallMessage(tool=tool, args=args))
            ),
            on_tool_result=lambda result, success: asyncio.create_task(
                self.send_message(websocket, ToolResultMessage(result=result, success=success))
            ),
            on_response=lambda text: asyncio.create_task(
                self.send_message(websocket, AgentResponseMessage(text=text))
            ),
            on_status=lambda status: asyncio.create_task(
                self.send_message(websocket, StatusUpdateMessage(status=status))
            )
        )
        
        try:
            # Send initial status
            await self.send_message(
                websocket,
                StatusUpdateMessage(status="idle", text="AZUL agent ready")
            )
            
            # Message loop
            async for message in websocket:
                try:
                    data = json.loads(message)
                    await self.handle_message(websocket, agent, data)
                except json.JSONDecodeError:
                    await self.send_message(
                        websocket,
                        ErrorMessage(error="Invalid JSON", details=str(message))
                    )
                except Exception as e:
                    logger.error(f"Error handling message: {e}", exc_info=True)
                    await self.send_message(
                        websocket,
                        ErrorMessage(error="Message handling error", details=str(e))
                    )
        
        except websockets.exceptions.ConnectionClosed:
            logger.info("Client disconnected")
        except Exception as e:
            logger.error(f"Error in client handler: {e}", exc_info=True)
    
    async def handle_message(
        self,
        websocket: WebSocketServerProtocol,
        agent: AzulAgent,
        data: dict
    ):
        """Handle a message from the client.
        
        Args:
            websocket: WebSocket connection
            agent: Agent instance
            data: Message data
        """
        message_type = data.get("type")
        
        if message_type == "user_prompt":
            # Parse user prompt
            try:
                user_msg = UserPromptMessage(**data)
            except Exception as e:
                await self.send_message(
                    websocket,
                    ErrorMessage(error="Invalid user_prompt message", details=str(e))
                )
                return
            
            # Execute agent in background task
            asyncio.create_task(self.execute_agent(websocket, agent, user_msg.text))
        
        else:
            await self.send_message(
                websocket,
                ErrorMessage(error=f"Unknown message type: {message_type}")
            )
    
    async def execute_agent(
        self,
        websocket: WebSocketServerProtocol,
        agent: AzulAgent,
        user_input: str
    ):
        """Execute the agent and handle the result.
        
        Args:
            websocket: WebSocket connection
            agent: Agent instance
            user_input: User's input text
        """
        try:
            # Execute agent in thread pool (blocking operation)
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, agent.execute, user_input)
            
            # Response is already sent via callbacks, but send status update
            await self.send_message(
                websocket,
                StatusUpdateMessage(status="idle", text="Ready for next task")
            )
        
        except Exception as e:
            logger.error(f"Error executing agent: {e}", exc_info=True)
            await self.send_message(
                websocket,
                ErrorMessage(error="Agent execution error", details=str(e))
            )
            await self.send_message(
                websocket,
                StatusUpdateMessage(status="error")
            )
    
    async def send_message(
        self,
        websocket: WebSocketServerProtocol,
        message: object
    ):
        """Send a message to the client.
        
        Args:
            websocket: WebSocket connection
            message: Message object (must have model_dump method)
        """
        try:
            # Convert Pydantic model to JSON
            if hasattr(message, 'model_dump'):
                data = message.model_dump()
            else:
                data = message
            
            await websocket.send(json.dumps(data))
        except Exception as e:
            logger.error(f"Error sending message: {e}", exc_info=True)
    
    async def start(self):
        """Start the WebSocket server."""
        logger.info(f"Starting AZUL server on ws://{self.host}:{self.port}")
        
        async with websockets.serve(self.handle_client, self.host, self.port):
            logger.info("Server started, waiting for connections...")
            await asyncio.Future()  # Run forever


def main():
    """Main entry point for the server."""
    server = AzulServer(
        host=config.websocket_host,
        port=config.websocket_port
    )
    
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")


if __name__ == "__main__":
    main()

