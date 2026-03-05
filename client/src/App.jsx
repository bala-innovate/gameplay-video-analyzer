import React, { useCallback, useState } from "react";
import Loader from "./components/Loader";
import VideoPlayer from "./components/VideoPlayer";
import AnnotationTimeline from "./components/AnnotationTimeline";
import GraphsPanel from "./components/GraphsPanel";
import StartTimesTimeline from "./components/StartTimesTimeline";

export default function App() {
  const [source, setSource] = useState(null);   // { src, name, isURL }
  const [schema, setSchema] = useState(null);   // { name }
  const [analysisResults, setAnalysisResults] = useState(null); // { [tagName]: number[] }
  const [startTimesName, setStartTimesName] = useState(null);
  const [panelOrder, setPanelOrder] = useState(["analysis", "annotations", "startTimes"]);
  const [collapsedPanels, setCollapsedPanels] = useState({
    analysis: false,
    annotations: false,
    startTimes: false,
  });
  const [draggingPanelId, setDraggingPanelId] = useState(null);
  const handleTimeUpdate = useCallback(() => {}, []);

  const onLoad = ({ src, name, isURL }) => {
    setSource({ src, name, isURL });
    setSchema(null);
    setStartTimesName(null);
    setAnalysisResults(null);
    window.dispatchEvent(new CustomEvent("vp:clear-annotations"));
    window.dispatchEvent(new CustomEvent("vp:clear-start-times"));
    window.dispatchEvent(new CustomEvent("vp:reset-schema"));
    window.dispatchEvent(new CustomEvent("vp:reset-start-times"));
  };
  const onClear = () => {
    setSource(null);
    setAnalysisResults(null);
  };

  const onSchemaLoaded = (name) => {
    setSchema({ name });
    setAnalysisResults(null);
  };
  const onSchemaClear = () => {
    setSchema(null);
    // tell the timeline to wipe itself
    window.dispatchEvent(new CustomEvent("vp:clear-annotations"));
    window.dispatchEvent(new CustomEvent("vp:reset-schema"));
    setAnalysisResults(null);
  };
  const onStartTimesClear = () => {
    setStartTimesName(null);
    window.dispatchEvent(new CustomEvent("vp:clear-start-times"));
    window.dispatchEvent(new CustomEvent("vp:reset-start-times"));
    setAnalysisResults(null);
  };

  const panelConfig = {
    analysis: {
      title: "Analysis",
      visible: !!analysisResults,
      render: () => (
        <GraphsPanel
          results={analysisResults}
          onClear={() => setAnalysisResults(null)}
          hideTitle
        />
      ),
    },
    annotations: {
      title: "Timeline: Action Annotations",
      visible: true,
      render: () => <AnnotationTimeline hasSource={true} hideTitle />,
    },
    startTimes: {
      title: "Start Times",
      visible: true,
      render: () => <StartTimesTimeline hasSource={true} hideTitle />,
    },
  };

  const visiblePanels = panelOrder.filter((id) => panelConfig[id]?.visible);

  const togglePanel = (panelId) => {
    setCollapsedPanels((prev) => ({ ...prev, [panelId]: !prev[panelId] }));
  };

  const reorderPanels = (fromId, toId) => {
    if (!fromId || !toId || fromId === toId) return;
    setPanelOrder((prev) => {
      const fromIdx = prev.indexOf(fromId);
      const toIdx = prev.indexOf(toId);
      if (fromIdx === -1 || toIdx === -1) return prev;
      const next = [...prev];
      const [moved] = next.splice(fromIdx, 1);
      next.splice(toIdx, 0, moved);
      return next;
    });
  };

  return (
    <div className="app">
      <header className="app__header">
        <h1>Gameplay Video Analyzer</h1>

        {/* Data status pills */}
        {source && (
          <>
            <div className={`src__status ${schema ? "is-ready" : "is-missing"}`} style={{ marginLeft: "auto" }}>
              <span className="src__pill is-file">Schema</span>
              <span className="src__name" title={schema?.name || "Not loaded"}>{schema?.name || "Not loaded"}</span>
              {schema && <button className="src__clear" onClick={onSchemaClear}>Clear</button>}
            </div>
            <div className={`src__status ${startTimesName ? "is-ready" : "is-missing"}`} style={{ marginLeft: 8 }}>
              <span className="src__pill is-file">Start Times</span>
              <span className="src__name" title={startTimesName || "Not loaded"}>{startTimesName || "Not loaded"}</span>
              {startTimesName && <button className="src__clear" onClick={onStartTimesClear}>Clear</button>}
            </div>
          </>
        )}

        {/* If no schema, push video pill to the right; if schema exists, keep spacing tight */}
        {source && (
          <div className="src__status" style={{ marginLeft: 8 }}>
            <span className={`src__pill ${source.isURL ? "is-url" : "is-file"}`}>
              {source.isURL ? "URL" : "File"}
            </span>
            <span className="src__name" title={source.name}>{source.name}</span>
            <button className="src__clear" onClick={onClear}>Clear</button>
          </div>
        )}
      </header>

      <main className="app__content">
        {!source && <Loader onLoad={onLoad} />}
        {source && (
          <>
          
            <VideoPlayer
              src={source.src}
              onTimeUpdate={handleTimeUpdate}
              onSchemaLoaded={onSchemaLoaded}
              onAnalysisComplete={(data) => setAnalysisResults(data)}
              backendUrl="http://127.0.0.1:5000"  //backendurl
              schemaLoaded={!!schema}
              onStartTimesLoaded={setStartTimesName} 
            />
            <div className="panelStack">
              {visiblePanels.map((panelId) => {
                const panel = panelConfig[panelId];
                const isCollapsed = !!collapsedPanels[panelId];
                return (
                  <section
                    key={panelId}
                    className={`panelCard ${isCollapsed ? "is-collapsed" : ""}`}
                  >
                    <header
                      className="panelCard__header"
                      draggable
                      onDragStart={(e) => {
                        setDraggingPanelId(panelId);
                        e.dataTransfer.setData("text/plain", panelId);
                        e.dataTransfer.effectAllowed = "move";
                      }}
                      onDragOver={(e) => e.preventDefault()}
                      onDrop={(e) => {
                        e.preventDefault();
                        const droppedId = e.dataTransfer.getData("text/plain") || draggingPanelId;
                        reorderPanels(droppedId, panelId);
                        setDraggingPanelId(null);
                      }}
                      onDragEnd={() => setDraggingPanelId(null)}
                      title="Drag to reorder"
                    >
                      <div className="panelCard__titleWrap">
                        <span className="panelCard__drag">⋮⋮</span>
                        <h2 className="panelCard__title">{panel.title}</h2>
                      </div>
                      <button
                        type="button"
                        className="panelCard__toggle"
                        onClick={() => togglePanel(panelId)}
                        aria-expanded={!isCollapsed}
                        title={isCollapsed ? "Expand section" : "Collapse section"}
                      >
                        {isCollapsed ? "Expand" : "Collapse"}
                      </button>
                    </header>
                    <div
                      className={`panelCard__content ${isCollapsed ? "is-hidden" : ""}`}
                      hidden={isCollapsed}
                    >
                      {panel.render()}
                    </div>
                  </section>
                );
              })}
            </div>
           

            
          </>
        )}
      </main>

      <footer className="app__footer">
        <small>Prototype · Upload → Playback → Scrub → Annotate → Analyze → Graph</small>
      </footer>
    </div>
  );
}
