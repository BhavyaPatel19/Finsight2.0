import { useEffect, useRef } from 'react'

const VERTEX_SHADER = `
  attribute vec2 a_position;
  void main() {
    gl_Position = vec4(a_position, 0.0, 1.0);
  }
`

const FRAGMENT_SHADER = `
  precision mediump float;
  uniform float u_time;
  uniform vec2 u_resolution;

  vec3 color1 = vec3(0.078, 0.561, 0.467); // #148F77
  vec3 color2 = vec3(0.102, 0.737, 0.612); // #1ABC9C
  vec3 color3 = vec3(0.106, 0.165, 0.290); // #1B2A4A
  vec3 color4 = vec3(0.031, 0.047, 0.078); // #080c14

  float noise(vec2 p) {
    return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453);
  }

  float smoothNoise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    float a = noise(i);
    float b = noise(i + vec2(1.0, 0.0));
    float c = noise(i + vec2(0.0, 1.0));
    float d = noise(i + vec2(1.0, 1.0));
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
  }

  float fbm(vec2 p) {
    float value = 0.0;
    float amplitude = 0.5;
    float frequency = 1.0;
    for(int i = 0; i < 5; i++) {
      value += amplitude * smoothNoise(p * frequency);
      frequency *= 2.0;
      amplitude *= 0.5;
    }
    return value;
  }

  void main() {
    vec2 uv = gl_FragCoord.xy / u_resolution.xy;
    vec2 p = uv * 3.0;
    float t = u_time * 0.15;

    vec2 flow1 = vec2(fbm(p + vec2(t * 0.5, t * 0.3)), fbm(p + vec2(t * 0.3, -t * 0.4)));
    vec2 flow2 = vec2(fbm(p + flow1 * 2.0 + vec2(t * 0.2, t * 0.25)), fbm(p + flow1 * 2.0 + vec2(-t * 0.3, t * 0.2)));

    float n1 = fbm(p + flow2 * 3.0 + vec2(t * 0.1, -t * 0.15));
    float n2 = fbm(p + flow2 * 2.5 + vec2(-t * 0.12, t * 0.18));
    float n3 = fbm(p + flow1 * 1.5 + vec2(t * 0.08, t * 0.1));

    float wave1 = sin(p.x * 2.0 + t + n1 * 3.0) * 0.5 + 0.5;
    float wave2 = sin(p.y * 2.5 - t * 0.8 + n2 * 2.5) * 0.5 + 0.5;
    float wave3 = sin((p.x + p.y) * 1.5 + t * 0.6 + n3 * 2.0) * 0.5 + 0.5;

    float blend = (n1 + n2 + n3) / 3.0;
    blend = smoothstep(0.2, 0.8, blend);

    vec3 color = mix(color4, color3, wave1);
    color = mix(color, color1, wave2 * blend);
    color = mix(color, color2, wave3 * (1.0 - blend) * 0.6);

    float vignette = 1.0 - length(uv - 0.5) * 0.8;
    color *= vignette;

    gl_FragColor = vec4(color, 1.0);
  }
`

function createShader(gl, type, source) {
  const shader = gl.createShader(type)
  if (!shader) return null
  gl.shaderSource(shader, source)
  gl.compileShader(shader)
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    console.error('Shader compile error:', gl.getShaderInfoLog(shader))
    gl.deleteShader(shader)
    return null
  }
  return shader
}

export default function ShaderBackground() {
  const canvasRef = useRef(null)
  const animRef = useRef(undefined)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const gl = canvas.getContext('webgl')
    if (!gl) return

    const vertexShader = createShader(gl, gl.VERTEX_SHADER, VERTEX_SHADER)
    const fragmentShader = createShader(gl, gl.FRAGMENT_SHADER, FRAGMENT_SHADER)
    if (!vertexShader || !fragmentShader) return

    const program = gl.createProgram()
    if (!program) return
    gl.attachShader(program, vertexShader)
    gl.attachShader(program, fragmentShader)
    gl.linkProgram(program)
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      console.error('Program link error:', gl.getProgramInfoLog(program))
      return
    }

    const posLoc = gl.getAttribLocation(program, 'a_position')
    const timeLoc = gl.getUniformLocation(program, 'u_time')
    const resLoc = gl.getUniformLocation(program, 'u_resolution')

    const buf = gl.createBuffer()
    gl.bindBuffer(gl.ARRAY_BUFFER, buf)
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([
      -1, -1, 1, -1, -1, 1,
      -1, 1, 1, -1, 1, 1,
    ]), gl.STATIC_DRAW)

    const resize = () => {
      const dpr = window.devicePixelRatio || 1
      canvas.width = canvas.clientWidth * dpr
      canvas.height = canvas.clientHeight * dpr
      gl.viewport(0, 0, canvas.width, canvas.height)
    }
    resize()
    window.addEventListener('resize', resize)

    const startTime = Date.now()
    const render = () => {
      const t = (Date.now() - startTime) / 1000
      gl.clearColor(0, 0, 0, 1)
      gl.clear(gl.COLOR_BUFFER_BIT)
      gl.useProgram(program)
      gl.enableVertexAttribArray(posLoc)
      gl.bindBuffer(gl.ARRAY_BUFFER, buf)
      gl.vertexAttribPointer(posLoc, 2, gl.FLOAT, false, 0, 0)
      gl.uniform1f(timeLoc, t)
      gl.uniform2f(resLoc, canvas.width, canvas.height)
      gl.drawArrays(gl.TRIANGLES, 0, 6)
      animRef.current = requestAnimationFrame(render)
    }
    render()

    return () => {
      window.removeEventListener('resize', resize)
      if (animRef.current) cancelAnimationFrame(animRef.current)
    }
  }, [])

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: 'absolute',
        inset: 0,
        width: '100%',
        height: '100%',
        display: 'block',
      }}
    />
  )
}
