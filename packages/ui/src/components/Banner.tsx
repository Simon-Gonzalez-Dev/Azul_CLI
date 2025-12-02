import React from "react";
import { Box, Text } from "ink";

const BANNER = `
    █████╗   ███████╗   ██╗   ██╗   ██╗       
   ██╔══██╗   ╚════██╗  ██║   ██║   ██║      
  ███████║    █████╔╝   ██║   ██║   ██║       
 ██╔══██║    ██╔═══╝    ██║   ██║   ██║       
██║  ██║     ███████╗   ╚██████╔╝   ███████╗  
╚═╝  ╚═╝     ╚══════╝    ╚═════╝    ╚══════╝ 

║   AI Coding Assistant - Universal Mode  ║
`;

interface BannerProps {
  // No props needed - banner is static
}

export const Banner: React.FC<BannerProps> = () => {
  return (
    <Box flexDirection="column" paddingX={1} paddingY={0}>
      <Text color="cyanBright">{BANNER}</Text>
    </Box>
  );
};

