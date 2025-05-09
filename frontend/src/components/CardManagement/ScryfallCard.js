import React, { useEffect, useState, useRef } from 'react';
import api from '../../utils/api';
import { Col, Divider, Image, Row, Space, Typography, Select, Card } from 'antd';
import { LinkOutlined } from '@ant-design/icons';
import SetSymbol from '../Shared/SetSymbol';
import ManaSymbol from '../Shared/ManaSymbol';
import LegalityTag from '../Shared/LegalityTag';
import { formatOracleText, formatCardName } from '../../utils/formatting';
import { languageLabelMap, labelToCodeMap, ALLOWED_QUALITIES } from '../../utils/constants';

const { Title, Text } = Typography;

const ScryfallCard = ({ data, isEditable, onChange }) => {
  if (!data) return null;
  // console.log ("ScryfallCard data recevied: ", data);
  
  const resolvedLanguageCode = labelToCodeMap[data?.language] || data?.language || 'en';

  const [availableLanguages, setAvailableLanguages] = useState([]);
  const [availableVersions, setAvailableVersions] = useState([]);
  const [displayData, setDisplayData] = useState(data);
  const [editingFields, setEditingFields] = useState(() => ({
    id: data?.id,
    buylist_id: data?.buylist_id,
    user_id: data?.user_id,
    name: data?.name,
    language: resolvedLanguageCode,
    quality: data?.quality || 'NM',
    quantity: data?.quantity || 1,
    set_code: data?.set_code,
    set_name: data?.set_name,
    version: data?.version || 'Standard',
    foil: data?.foil ?? false,
  }));
  
  const currentPrintingRef = useRef(null);
  const hasInitializedRef = useRef(false); 

  const [isLoading, setIsLoading] = useState(false);
  
  const [hoveredPrinting, setHoveredPrinting] = useState(null);
  const [isFront, setIsFront] = useState(true);
  const [allPrintings, setAllPrintings] = useState([]);
  const isDoubleFaced = Array.isArray(data?.scryfall?.card_faces) && data?.scryfall?.card_faces.length === 2;
  const selectedPrintingIdRef = useRef(null);

  const handleFieldChange = (field, value) => {
    setEditingFields(prev => {
      const updated = { ...prev, [field]: value };
      // console.log(`[handleFieldChange] ${field}: ${prev[field]} → ${value}`);
      if (onChange) onChange(updated);
      return updated;
    });
  };

  useEffect(() => {
    if (!allPrintings.length || hasInitializedRef.current) return;
  
    const matched = allPrintings.find(p =>
      p.id === selectedPrintingIdRef.current ||
      (p.set_code === data.set_code && p.name === data.name) ||
      p.id === data.scryfall.id
    ) || allPrintings[0];
  
    if (!matched) return;
  
    hasInitializedRef.current = true;
    selectedPrintingIdRef.current = matched.id;
    currentPrintingRef.current = matched;
  
    setDisplayData({ ...data.scryfall, ...matched });
  
    setEditingFields(prev => ({
      ...prev,
      set_code: matched.set_code,
      set_name: matched.set_name,
      foil: matched.finishes?.includes('foil') || false,
      version: matched.version || 'Standard',
      language: labelToCodeMap[data?.language] || matched.lang || 'en',
    }));
  }, [allPrintings, data]);
  
  useEffect(() => {
    if (!displayData || !displayData?.id || !Array.isArray(allPrintings)) {
      return;
    }

    const printingMeta = allPrintings.find(p => p.id === displayData?.id);
    console.log("printingMeta:", printingMeta);
    if (printingMeta?.available_languages) {
      const structured = printingMeta.available_languages.map(lang => ({
        label: languageLabelMap[lang] || lang,
        value: lang,
      }));
      // console.log("[Lang] Updating languages to:", structured);
      setAvailableLanguages(structured);
    } else {
      console.warn("No language metadata found for current printing.");
      setAvailableLanguages([]);
    }
  }, [displayData?.id, allPrintings]);

  useEffect(() => {
    if (availableLanguages.length && !availableLanguages.find(l => l.value === editingFields.language)) {
      setEditingFields(prev => ({
        ...prev,
        language: 'en'
      }));
    }
  }, [availableLanguages]);
  
  useEffect(() => {
    const printings = data.scryfall?.all_printings ?? [];
    if (!Array.isArray(printings)) return;
  
    const enriched = printings.filter(p => !p.digital);
    const needsEnhancement = enriched.filter(p => {
      const isDFC = ['transform', 'modal_dfc', 'double_faced_token'].includes(p.layout);
      return isDFC || !p.image_uris?.normal;
    });
  
    const updatePrintings = async () => {
      const enhanced = await Promise.all(
        needsEnhancement.map(p =>
          api.get(`/scryfall/card/${p.id}`).then(res => ({ ...p, ...res.data })).catch(() => p)
        )
      );
  
      const merged = enriched.map(p => enhanced.find(ep => ep.id === p.id) || p);
      setAllPrintings(merged);
    };
  
    updatePrintings();
  }, [data?.scryfall?.id]);
  
  useEffect(() => {
    if (!displayData) return;
  
    const versions = displayData.available_versions;
    // console.log("[Version] From displayData.available_versions:", versions);
  
    if (!versions) {
      setAvailableVersions([]);
      return;
    }
  
    const versionSet = new Set();
  
    (versions.finishes || []).forEach(f => {
      if (f === 'foil') versionSet.add('Foil');
      if (f === 'etched') versionSet.add('Etched');
      if (f === 'nonfoil') versionSet.add('Standard');
    });
  
    (versions.frame_effects || []).forEach(fx => {
      if (fx === 'showcase') versionSet.add('Showcase');
      if (fx === 'extendedart') versionSet.add('Extended Art');
    });
  
    if (versions.full_art) versionSet.add('Full Art');
    if (versions.textless) versionSet.add('Textless');
    if (versions.border_color === 'borderless') versionSet.add('Borderless');
  
    const versionArray = Array.from(versionSet);
    // console.log("[Version] Available dropdown values:", versionArray);
    setAvailableVersions(versionArray);
  }, [displayData]);

  useEffect(() => {
    if (
      availableVersions.length > 0 &&
      !availableVersions.includes(editingFields.version)
    ) {
      setEditingFields(prev => ({
        ...prev,
        version: availableVersions.includes('Standard') ? 'Standard' : availableVersions[0],
      }));
    }
  }, [availableVersions, editingFields.version]);

  useEffect(() => {
    hasInitializedRef.current = false;
  }, [data?.scryfall?.id]);

  const handlePrintClick = (print) => {
    selectedPrintingIdRef.current = print.id;
    currentPrintingRef.current = print;
  
    const merged = {
      ...print,
      available_versions: print.available_versions || {}
    };
  
    setDisplayData(merged);
  
    const group = allPrintings.filter(p =>
      p.set_code === print.set_code &&
      p.collector_number === print.collector_number
    );
    const englishPrint = group.find(p => p.lang === 'en');
    const versionOptions = englishPrint?.available_versions || {};
  
    const dynamicVersions = new Set();
    (versionOptions.finishes || []).forEach(f => {
      if (f === 'foil') dynamicVersions.add('Foil');
      if (f === 'etched') dynamicVersions.add('Etched');
      if (f === 'nonfoil') dynamicVersions.add('Standard');
    });
    (versionOptions.frame_effects || []).forEach(effect => {
      if (effect === 'showcase') dynamicVersions.add('Showcase');
      if (effect === 'extendedart') dynamicVersions.add('Extended Art');
    });
    if (versionOptions.full_art) dynamicVersions.add('Full Art');
    if (versionOptions.textless) dynamicVersions.add('Textless');
    if (versionOptions.border_color === 'borderless') {
      dynamicVersions.add('Borderless');
    }
  
    const versions = Array.from(dynamicVersions);
    setAvailableVersions(versions);
  
    setEditingFields(prev => {
      const updated = {
        ...prev,
        set_code: print.set_code,
        set_name: print.set_name,
        foil: print.finishes?.includes('foil') || false,
        language: print.lang || 'en',
        version: versions.includes('Standard') ? 'Standard' : versions[0],
      };
      if (onChange) onChange(updated);
      return updated;
    });
  };
  
  const handleImageHover = (print) => setHoveredPrinting(print);

  const handleImageLeave = () => setHoveredPrinting(null);

  const toggleFace = () => setIsFront(prev => !prev);

  const getDisplayImage = () => {
    const src = (() => {
      const source = hoveredPrinting || displayData;
      if (!source) return '';
  
      const faces = source.card_faces;
      if (Array.isArray(faces) && faces.length === 2) {
        return faces[isFront ? 0 : 1]?.image_uris?.normal;
      }
      return source.image_uris?.normal;
    })();
    return src || '';
  };

  const renderedPrintings = allPrintings.map((print, index) => {
    const isSelected = displayData?.id === print.id;
    let imageSrc = '';
  
    if (Array.isArray(print.card_faces) && print.card_faces.length === 2) {
      imageSrc = print.card_faces[isFront ? 0 : 1]?.image_uris?.small || '';
    } else if (print.image_uris?.small) {
      imageSrc = print.image_uris.small;
    } else if (data.scryfall?.card_faces?.length === 2) {
      imageSrc = data.scryfall.card_faces[isFront ? 0 : 1]?.image_uris?.small || '';
    } else {
      imageSrc = data.scryfall?.image_uris?.small || '';
    }
    // console.log("renderedPrintings imageSrc: ", imageSrc)
    // console.log("renderedPrintings index, print: ", index, print)
    return (
      <div
        key={print.id}
        onClick={() => handlePrintClick(print)}
        onMouseEnter={() => handleImageHover(print)}
        onMouseLeave={handleImageLeave}
        style={{
          display: 'inline-block',
          textAlign: 'center',
          marginRight: 8,
          cursor: 'pointer',
          border: isSelected ? '2px solid #1890ff' : '1px solid #ccc',
          borderRadius: 4,
          padding: 4,
          width: 56,
        }}
      >
        {imageSrc ? (
        <Image 
          src={imageSrc} 
          preview={false}
          style={{ width: 48, height: 68, cursor: 'pointer' }} 
          onClick={() => handlePrintClick(print)}
        />
      ) : (
        <div style={{ width: 48, height: 68, backgroundColor: '#eee' }} />
      )}
      <div style={{ fontSize: 12, marginTop: 4, color: '#666' }}>
        {print.prices?.usd
          ? `$${print.prices.usd}`
          : print.prices?.usd_foil
          ? `$${print.prices.usd_foil}*`
          : 'N/A'}
      </div>
    </div>
  );
});
  
  return (
    <Card className="scryfall-card" style={{ background: "#f7f7f7", borderRadius: '8px' }}>
      <Row gutter={16}>
        <Col span={8}>
          {isLoading ? (
            <div>Loading...</div>
          ) : (
            <>
              <div style={{ position: 'relative' }}>
                <Image
                  src={getDisplayImage()}
                  alt={displayData?.name}
                  style={{ width: '100%', borderRadius: '4px' }}
                  onMouseEnter={() => handleImageHover(displayData)}
                  onMouseLeave={handleImageLeave}
                />
                {isDoubleFaced && (
                  <div style={{ marginTop: 8, display: 'flex', justifyContent: 'center' }}>
                    <button
                      onClick={toggleFace}
                      style={{
                        backgroundColor: '#f0f0f0',
                        border: '1px solid #d9d9d9',
                        borderRadius: '6px',
                        padding: '4px 12px',
                        fontSize: '0.875rem',
                        fontWeight: 500,
                        color: '#333',
                        cursor: 'pointer',
                        transition: 'all 0.3s ease',
                      }}
                    >
                      {isFront ? 'Back' : 'Front'}
                    </button>
                  </div>
                )}
              </div>
              <Divider />
              <Space direction="vertical" size="small">
                <Text><strong>Mana Value:</strong> {data?.scryfall?.cmc ?? 'N/A'}</Text>
                <Text><strong>Types:</strong> {data?.scryfall?.type_line ?? 'N/A'}</Text>
                <Text><strong>Rarity:</strong> {displayData?.rarity ?? 'N/A'}</Text>
                <Text>
                  <strong>Expansion:</strong>{' '}
                  {displayData.set_name ? (
                    <>
                      <SetSymbol
                        setCode={displayData.set_code}
                        rarity={displayData.rarity}
                        collector_number={displayData.collector_number}
                      />
                      {displayData.set_name}
                    </>
                  ) : 'N/A'}
                </Text>
                <Text><strong>Card Number:</strong> {displayData?.collector_number ?? 'N/A'}</Text>
                <Text><strong>Artist:</strong> {displayData?.artist ?? 'N/A'}</Text>
              </Space>
            </>
          )}
          <Divider orientation="left">Available Printings</Divider>
          <div style={{ marginBottom: '16px' }}>{renderedPrintings}</div>
          <Divider />
          <Space direction="vertical">
            {data?.scryfall?.scryfall_uri && (
              <a href={data.scryfall.scryfall_uri} target="_blank" rel="noopener noreferrer">
                <LinkOutlined /> View on Scryfall
              </a>
            )}
            {data?.scryfall?.multiverse_ids?.[0] && (
              <a
                href={`https://gatherer.wizards.com/Pages/Card/Details.aspx?multiverseid=${data.scryfall.multiverse_ids[0]}`}
                target="_blank"
                rel="noopener noreferrer"
              >
                <LinkOutlined /> View on Gatherer
              </a>
            )}
            <a
              href={`https://edhrec.com/cards/${formatCardName(data?.scryfall?.name || '')}`}
              target="_blank"
              rel="noopener noreferrer"
            >
              <LinkOutlined /> Card analysis on EDHREC
            </a>
          </Space>
        </Col>
        <Col span={16}>
          <Title level={3}>
            {data?.scryfall?.name}
            <span className="mana-cost">
              {data?.scryfall?.mana_cost &&
                data.scryfall.mana_cost.split('').map((char, index) =>
                  char === '{' || char === '}' ? null : (
                    <ManaSymbol key={index} symbol={`{${char}}`} />
                  )
                )}
            </span>
          </Title>
          <Text strong>
            {displayData?.set_name} ({displayData?.set_code?.toUpperCase() ?? 'N/A'})
          </Text>
          <Divider />
          <Text>{data?.scryfall?.type_line ?? 'N/A'}</Text>
          {data?.scryfall?.oracle_text && formatOracleText(data.scryfall.oracle_text)}
          {data?.scryfall?.flavor_text && <Text italic>{data.scryfall.flavor_text}</Text>}
          <Text>
            {data?.scryfall?.power && data?.scryfall?.toughness
              ? `${data.scryfall.power}/${data.scryfall.toughness}`
              : ''}
          </Text>
          <Divider />
          <Title level={4}>Format Legality</Title>
          <Row gutter={[16, 8]}>
            {Object.entries(data?.scryfall?.legalities ?? {}).map(([format, legality], index) => (
              <Col span={12} key={index}>
                <LegalityTag format={format} legality={legality} />
              </Col>
            ))}
          </Row>
          <Divider />
          {isEditable && editingFields && (
            <>
              <Title level={5}>Edit Preferences</Title>
              <Space direction="vertical" style={{ marginBottom: 16 }}>
                <div>
                  <Text strong>Language: </Text>
                  <Select
                    value={editingFields.language}
                    onChange={(val) => handleFieldChange('language', val)}
                    style={{ width: 200 }}
                    options={availableLanguages}
                  />
                </div>
                <div>
                  <Text strong>Quality: </Text>
                  <Select
                    value={editingFields.quality}
                    onChange={(val) => handleFieldChange('quality', val)}
                    style={{ width: 200 }}
                  >
                    {ALLOWED_QUALITIES.map((q) => (
                      <Select.Option key={q} value={q}>{q}</Select.Option>
                    ))}
                  </Select>
                </div>
                <div>
                  <Text strong>Version: </Text>
                  <Select
                    value={editingFields.version}
                    onChange={(val) => handleFieldChange('version', val)}
                    style={{ width: 200 }}
                  >
                    {availableVersions.map((v) => (
                      <Select.Option key={v} value={v}>{v}</Select.Option>
                    ))}
                  </Select>
                </div>
              </Space>
            </>
          )}
        </Col>
      </Row>
    </Card>
  );
};
  

export default React.memo(ScryfallCard);
