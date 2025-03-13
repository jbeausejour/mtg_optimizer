import React, { useState } from 'react';
import { useLocation } from 'react-router-dom';
import { Button, Input, message } from 'antd';
import api from '../../utils/api';

const { TextArea } = Input;

const ImportCardsToBuylist = ({ buylistId, onCardsAdded, userId, cardText, setCardText, errorCards, setErrorCards }) => {
  const location = useLocation();

  const parseCardList = (text) => {
    const lines = text.split('\n');
    const cards = [];

    const formatRegex = [
      /^(?<quantity>\d+)\s*x?\s*(?<name>.+)$/i, // Format 2 and 3
      /^(?<name>.+)$/i, // Format 1
    ];

    for (const line of lines) {
      const trimmedLine = line.trim();
      if (!trimmedLine) continue;

      let matched = false;
      for (const regex of formatRegex) {
        const match = trimmedLine.match(regex);
        if (match) {
          const { quantity, name } = match.groups;
          cards.push({
            name: name.trim(),
            quantity: parseInt(quantity || 1, 10),
          });
          matched = true;
          break;
        }
      }

      if (!matched) {
        setErrorCards((prev) => [...prev, trimmedLine]);
      }
    }

    return cards;
  };

  const handleImport = async () => {
    if (!cardText.trim()) {
      message.error("Please paste a card list.");
      return;
    }

    //message.info("using buylistId: " + buylistId);
    const cards = parseCardList(cardText);
    if (cards.length === 0) {
        message.error("No valid cards found.");
        return;
    }

    try {
        const response = await api.post("/buylist/cards/import", {
            id: buylistId,
            cards,
            user_id: userId,
        });

        const { addedCards = [], notFoundCards = [] } = response.data; // ✅ Default to empty arrays

        if (addedCards.length) {
            message.success(`${addedCards.length} cards added to the buylist.`);
            onCardsAdded(addedCards);
        }
        if (notFoundCards.length) {
          message.error(`${notFoundCards.length} cards could not be found.`);
          setErrorCards(notFoundCards.map((card) => card.name)); // ✅ Store only the latest errors
        }

        // ✅ Remove successfully added cards from the input box
        const addedCardNames = new Set(addedCards.map((card) => card.name));
        const remainingCards = cards
            .filter((card) => notFoundCards.some((nf) => nf.name === card.name)) // ✅ Keep only not found cards
            .map((card) => card.name)
            .join("\n");

        setCardText(remainingCards); // ✅ Now only shows failed cards

    } catch (error) {
        message.error("Failed to import cards. Please try again.");
        console.error("Import Error:", error);
    }
  };

  return (
    <div>
        <h3>Import Cards to Buylist</h3>
        <TextArea
            value={cardText}
            onChange={(e) => setCardText(e.target.value)}
            placeholder="Paste your card list here... &#10;Format:&#10;Card Name&#10;2 Card Name&#10;3x Card Name"
            rows={10}
            style={{ resize: 'both' }}
        />
        <Button type="primary" onClick={handleImport} style={{ marginTop: 10 }}>
            Import Cards
        </Button>
        {errorCards.length > 0 && (
            <div style={{ marginTop: 20, color: 'red' }}>
                <strong>Errors:</strong>
                <ul>
                    {errorCards.map((card, index) => (
                        <li key={index}>{card}</li>
                    ))}
                </ul>
            </div>
        )}
    </div>
  );
};

export default ImportCardsToBuylist;