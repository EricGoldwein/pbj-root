import { useState, useEffect } from 'react';

/**
 * Hook that creates a typing effect for text
 */
export function useTypingEffect(
  text: string,
  speed: number = 30,
  delay: number = 0
): string {
  const [displayedText, setDisplayedText] = useState('');
  const [isTyping, setIsTyping] = useState(false);

  useEffect(() => {
    if (delay > 0 && !isTyping) {
      const delayTimer = setTimeout(() => {
        setIsTyping(true);
      }, delay);
      return () => clearTimeout(delayTimer);
    } else if (delay === 0) {
      setIsTyping(true);
    }
  }, [delay, isTyping]);

  useEffect(() => {
    if (!isTyping) return;

    setDisplayedText('');
    let currentIndex = 0;

    const typingTimer = setInterval(() => {
      if (currentIndex < text.length) {
        setDisplayedText(text.slice(0, currentIndex + 1));
        currentIndex++;
      } else {
        clearInterval(typingTimer);
        // Ensure we set the full text when complete
        setDisplayedText(text);
      }
    }, speed);

    return () => clearInterval(typingTimer);
  }, [text, speed, isTyping]);

  return displayedText;
}

