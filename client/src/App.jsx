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
  const handleTimeUpdate = useCallback(() => {}, []);

  const onLoad = ({ src, name, isURL }) => {
    setSource({ src, name, isURL });
    setAnalysisResults(null);
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
    setAnalysisResults(null);
  };

  return (
    <div className="app">
      <header className="app__header">
        <h1>Gameplay Video Analyzer</h1>

        {/* Schema pill (left of video pill) */}
        {schema && (
          <div className="src__status" style={{ marginLeft: "auto" }}>
            <span className="src__pill is-file">Schema</span>
            <span className="src__name" title={schema.name}>{schema.name}</span>
            <button className="src__clear" onClick={onSchemaClear}>Clear</button>
          </div>
        )}

        {/* If no schema, push video pill to the right; if schema exists, keep spacing tight */}
        {source && (
          <div className="src__status" style={{ marginLeft: schema ? 8 : "auto" }}>
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
              modelPath="/models/model.tflite"
              backendUrl="http://127.0.0.1:5000"  //backendurl
              schemaLoaded={!!schema}
              onStartTimesLoaded={setStartTimesName} 
            />
            {analysisResults && (
              <GraphsPanel results={analysisResults} onClear={() => setAnalysisResults(null)} />
            )} 
            <AnnotationTimeline hasSource={true} />
            <StartTimesTimeline hasSource={true} />
           

            
          </>
        )}
      </main>

      <footer className="app__footer">
        <small>Prototype · Upload → Playback → Scrub → Annotate → Analyze → Graph</small>
      </footer>
    </div>
  );
}
