package main

import (
    "context"
    "fmt"
    "log"
    
    "github.com/openclaw/sdk/plugin"
)

// ExamplePlugin implements a minimal OpenClaw plugin in Go
type ExamplePlugin struct {
    plugin.Base
}

func (p *ExamplePlugin) Name() string {
    return "go-example-plugin"
}

func (p *ExamplePlugin) Version() string {
    return "1.0.0"
}

func (p *ExamplePlugin) Execute(ctx context.Context, req *plugin.Request) (*plugin.Response, error) {
    // Sandbox: No filesystem access, no network, limited memory
    return &plugin.Response{
        Data: map[string]interface{}{
            "message": "Hello from Go plugin!",
            "runtime": "go1.21",
        },
    }, nil
}

func main() {
    p := &ExamplePlugin{}
    if err := plugin.Serve(p); err != nil {
        log.Fatal(err)
    }
}
