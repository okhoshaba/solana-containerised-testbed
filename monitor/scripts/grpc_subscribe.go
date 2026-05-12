package main

import (
	"context"
	"fmt"
	"log"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"

	"solana-latency-research/internal/utils"
)

func main() {
	// This script quickly validates Yellowstone gRPC connectivity without interfering with the main process.
	cfg, err := utils.LoadConfig("configs/config.example.yaml")
	if err != nil {
		log.Fatalf("failed to load config: %v", err)
	}

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	conn, err := grpc.DialContext(
		ctx,
		cfg.GRPC,
		grpc.WithBlock(),
		grpc.WithReturnConnectionError(),
		grpc.WithTransportCredentials(insecure.NewCredentials()),
	)
	if err != nil {
		log.Fatalf("gRPC connectivity check failed: %v", err)
	}
	defer conn.Close()

	fmt.Println("Yellowstone gRPC connectivity check succeeded")
}
